import os

import orjson
from django.conf import settings
from django.test import override_settings
from typing_extensions import ParamSpec

from zerver.lib.cache import cache_delete, get_realm_used_upload_space_cache_key
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import create_s3_buckets, find_key_by_email, use_s3_backend
from zerver.lib.upload import (
    create_attachment,
    sanitize_name,
    upload_backend,
    upload_message_attachment,
)
from zerver.lib.upload.s3 import S3UploadBackend
from zerver.lib.utils import assert_is_not_none
from zerver.models import Attachment, PreregistrationRealm, Realm
from zerver.models.realms import get_realm
from zerver.views.tusd import TusEvent, TusHook, TusHTTPRequest, TusUpload

ParamT = ParamSpec("ParamT")


class TusdHooksTest(ZulipTestCase):
    def test_non_localhost(self) -> None:
        request = TusHook(
            type="pre-create",
            event=TusEvent(
                http_request=TusHTTPRequest(
                    method="PATCH", uri="/api/v1/tus/thing", remote_addr="12.34.56.78", header={}
                ),
                upload=TusUpload(
                    id="",
                    is_final=False,
                    is_partial=False,
                    meta_data={
                        "filename": "zulip.txt",
                        "filetype": "text/plain",
                        "name": "zulip.txt",
                        "type": "text/plain",
                    },
                    offset=0,
                    partial_uploads=None,
                    size=1234,
                    size_is_deferred=False,
                    storage=None,
                ),
            ),
        )

        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
            REMOTE_ADDR="1.2.3.4",
        )
        self.assertEqual(result.status_code, 403)
        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(result.status_code, 200)

    def test_invalid_hook(self) -> None:
        self.login("hamlet")
        request = TusHook(
            type="bogus",
            event=TusEvent(
                http_request=TusHTTPRequest(
                    method="PATCH", uri="/api/v1/tus/thing", remote_addr="12.34.56.78", header={}
                ),
                upload=TusUpload(
                    id="",
                    is_final=False,
                    is_partial=False,
                    meta_data={
                        "filename": "zulip.txt",
                        "filetype": "text/plain",
                        "name": "zulip.txt",
                        "type": "text/plain",
                    },
                    offset=0,
                    partial_uploads=None,
                    size=1234,
                    size_is_deferred=False,
                    storage=None,
                ),
            ),
        )
        result = self.client_post(
            "/api/internal/tusd", request.model_dump(), content_type="application/json"
        )
        self.assertEqual(result.status_code, 404)

    def test_invalid_payload(self) -> None:
        result = self.client_post(
            "/api/internal/tusd",
            {"type": "pre-create", "event": "moose"},
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 400)


class TusdPreCreateTest(ZulipTestCase):
    def request(self, key: str = "") -> TusHook:
        return TusHook(
            type="pre-create",
            event=TusEvent(
                http_request=TusHTTPRequest(
                    method="PATCH", uri="/api/v1/tus/thing", remote_addr="12.34.56.78", header={}
                ),
                upload=TusUpload(
                    id="",
                    is_final=False,
                    is_partial=False,
                    meta_data={
                        "filename": "zulip.txt",
                        "filetype": "text/plain",
                        "name": "zulip.txt",
                        "type": "text/plain",
                        "key": key,
                    },
                    offset=0,
                    partial_uploads=None,
                    size=1234,
                    size_is_deferred=False,
                    storage=None,
                ),
            ),
        )

    def test_tusd_pre_create_hook(self) -> None:
        self.login("hamlet")
        result = self.client_post(
            "/api/internal/tusd",
            self.request().model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json.get("HttpResponse", None), None)
        self.assertEqual(result_json.get("RejectUpload", False), False)
        self.assertEqual(list(result_json["ChangeFileInfo"].keys()), ["ID"])
        self.assertTrue(result_json["ChangeFileInfo"]["ID"].endswith("/zulip.txt"))

    def test_unauthed_rejected(self) -> None:
        result = self.client_post(
            "/api/internal/tusd",
            self.request().model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 401)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]), {"message": "Unauthenticated upload"}
        )
        self.assertEqual(result_json["RejectUpload"], True)

    def test_api_key_auth(self) -> None:
        user_profile = self.example_user("hamlet")
        result = self.client_post(
            "/api/internal/tusd",
            self.request().model_dump(),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user_profile),
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json.get("HttpResponse", None), None)
        self.assertEqual(result_json.get("RejectUpload", False), False)
        self.assertEqual(list(result_json["ChangeFileInfo"].keys()), ["ID"])
        self.assertTrue(result_json["ChangeFileInfo"]["ID"].endswith("/zulip.txt"))

    def test_api_key_bad_auth(self) -> None:
        result = self.client_post(
            "/api/internal/tusd",
            self.request().model_dump(),
            content_type="application/json",
            HTTP_AUTHORIZATION="Digest moose",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 401)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]), {"message": "Unauthenticated upload"}
        )
        self.assertEqual(result_json["RejectUpload"], True)

    def test_sanitize_filename(self) -> None:
        self.login("hamlet")
        request = self.request()
        request.event.upload.meta_data["filename"] = "some 例 thing! ... like this?"
        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertTrue(result_json["ChangeFileInfo"]["ID"].endswith("/some-thing-...-like-this"))

    @override_settings(MAX_FILE_UPLOAD_SIZE=1)  # In MB
    def test_file_too_big_failure(self) -> None:
        self.login("hamlet")
        request = self.request()
        request.event.upload.size = 1024 * 1024 * 5  # 5MB
        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
        )

        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 413)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {
                "message": "File is larger than this server's configured maximum upload size (1 MiB)."
            },
        )
        self.assertEqual(result_json["RejectUpload"], True)

    @override_settings(MAX_FILE_UPLOAD_SIZE=1)  # In MB
    def test_file_too_big_failure_limited(self) -> None:
        self.login("hamlet")
        request = self.request()
        request.event.upload.size = 1024 * 1024 * 5  # 5MB

        realm = get_realm("zulip")
        realm.plan_type = Realm.PLAN_TYPE_LIMITED
        realm.save()

        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
        )

        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 413)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {
                "message": "File is larger than the maximum upload size (1 MiB) allowed by "
                "your organization's plan."
            },
        )
        self.assertEqual(result_json["RejectUpload"], True)

    def test_deferred_size(self) -> None:
        self.login("hamlet")
        request = self.request()
        request.event.upload.size = None
        request.event.upload.size_is_deferred = True
        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 411)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {"message": "SizeIsDeferred is not supported"},
        )
        self.assertEqual(result_json["RejectUpload"], True)

    def test_quota_exceeded(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")

        # We fake being almost at quota
        realm = hamlet.realm
        realm.custom_upload_quota_gb = 1
        realm.save(update_fields=["custom_upload_quota_gb"])

        path_id = upload_message_attachment("zulip.txt", "text/plain", b"zulip!", hamlet)[
            0
        ].removeprefix("/user_uploads/")
        attachment = Attachment.objects.get(path_id=path_id)
        attachment.size = assert_is_not_none(realm.upload_quota_bytes()) - 10
        attachment.save(update_fields=["size"])
        cache_delete(get_realm_used_upload_space_cache_key(realm.id))

        result = self.client_post(
            "/api/internal/tusd",
            self.request().model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 413)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {"message": "Upload would exceed your organization's upload quota."},
        )
        self.assertEqual(result_json["RejectUpload"], True)

    def test_realm_import_data_upload(self) -> None:
        # Choose import from slack
        email = "ete-slack-import@zulip.com"
        self.submit_realm_creation_form(
            email,
            realm_subdomain="ete-slack-import",
            realm_name="Slack import end to end",
            import_from="slack",
        )
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.data_import_metadata["import_from"], "slack")
        prereg_realm.data_import_metadata["import_from"] = "slack"
        prereg_realm.save()

        confirmation_key = find_key_by_email(email)
        assert confirmation_key is not None

        with self.assertLogs(level="WARNING") as warn_log:
            result = self.client_post(
                "/api/internal/tusd",
                self.request(key=confirmation_key).model_dump(),
                content_type="application/json",
            )
        self.assertEqual(result.status_code, 200)
        # Verify if we tried to remove any existing upload.
        self.assertEqual(
            warn_log.output,
            ["WARNING:root:slack.zip does not exist. Its entry in the database will be removed."],
        )
        result_json = result.json()
        self.assertEqual(result_json.get("HttpResponse", None), None)
        self.assertEqual(result_json.get("RejectUpload", False), False)
        self.assertEqual(list(result_json["ChangeFileInfo"].keys()), ["ID"])
        filename = f"import/{prereg_realm.id}/slack.zip"
        self.assertTrue(result_json["ChangeFileInfo"]["ID"].endswith(filename))

        info = TusUpload(
            id=filename,
            size=len("zulip!"),
            offset=0,
            size_is_deferred=False,
            meta_data={
                "filename": filename,
                "filetype": "text/plain",
                "name": "zulip.zip",
                "type": "text/plain",
                "key": confirmation_key,
            },
            is_final=False,
            is_partial=False,
            partial_uploads=None,
            storage=None,
        )
        request = TusHook(
            type="pre-finish",
            event=TusEvent(
                upload=info,
                http_request=TusHTTPRequest(
                    method="PATCH",
                    uri=f"/api/v1/tus/{info.id}",
                    remote_addr="12.34.56.78",
                    header={},
                ),
            ),
        )

        # Post the hook saying the file is in place
        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
        )

        self.assertEqual(result.status_code, 200)
        prereg_realm.refresh_from_db()
        self.assertTrue(
            prereg_realm.data_import_metadata["uploaded_import_file_name"].endswith(filename)
        )

    def test_realm_import_data_upload_size_is_deferred(self) -> None:
        # Choose import from slack
        email = "ete-slack-import@zulip.com"
        self.submit_realm_creation_form(
            email,
            realm_subdomain="ete-slack-import",
            realm_name="Slack import end to end",
            import_from="slack",
        )
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.data_import_metadata["import_from"], "slack")
        prereg_realm.data_import_metadata["import_from"] = "slack"
        prereg_realm.save()

        confirmation_key = find_key_by_email(email)
        assert confirmation_key is not None

        request = self.request(key=confirmation_key)
        request.event.upload.size = None
        request.event.upload.size_is_deferred = True
        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 411)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {"message": "SizeIsDeferred is not supported"},
        )
        self.assertEqual(result_json["RejectUpload"], True)

    def test_realm_import_data_upload_size_limit_exceeded(self) -> None:
        # Choose import from slack
        email = "ete-slack-import@zulip.com"
        self.submit_realm_creation_form(
            email,
            realm_subdomain="ete-slack-import",
            realm_name="Slack import end to end",
            import_from="slack",
        )
        prereg_realm = PreregistrationRealm.objects.get(email=email)
        self.assertEqual(prereg_realm.data_import_metadata["import_from"], "slack")
        prereg_realm.data_import_metadata["import_from"] = "slack"
        prereg_realm.save()

        confirmation_key = find_key_by_email(email)
        assert confirmation_key is not None

        request = self.request(key=confirmation_key)

        assert settings.MAX_WEB_DATA_IMPORT_SIZE_MB is not None
        max_upload_size = settings.MAX_WEB_DATA_IMPORT_SIZE_MB * 1024 * 1024
        request.event.upload.size = max_upload_size + 1
        result = self.client_post(
            "/api/internal/tusd",
            request.model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 413)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {
                "message": f"Uploaded file exceeds the maximum file size for imports ({settings.MAX_WEB_DATA_IMPORT_SIZE_MB} MiB)."
            },
        )
        self.assertEqual(result_json["RejectUpload"], True)


class TusdPreFinishTest(ZulipTestCase):
    def request(self, info: TusUpload) -> TusHook:
        return TusHook(
            type="pre-finish",
            event=TusEvent(
                upload=info,
                http_request=TusHTTPRequest(
                    method="PATCH",
                    uri=f"/api/v1/tus/{info.id}",
                    remote_addr="12.34.56.78",
                    header={},
                ),
            ),
        )

    def test_tusd_pre_finish_hook(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Act like tusd does -- put the file and its .info in place
        path_id = upload_backend.generate_message_upload_path(
            str(hamlet.realm.id), sanitize_name("zulip.txt")
        )
        upload_backend.upload_message_attachment(
            path_id, "zulip.txt", "text/plain", b"zulip!", hamlet
        )

        info = TusUpload(
            id=path_id,
            size=len("zulip!"),
            offset=0,
            size_is_deferred=False,
            meta_data={
                "filename": "zulip.txt",
                "filetype": "text/plain",
                "name": "zulip.txt",
                "type": "text/plain",
            },
            is_final=False,
            is_partial=False,
            partial_uploads=None,
            storage=None,
        )
        upload_backend.upload_message_attachment(
            f"{path_id}.info",
            "zulip.txt.info",
            "application/octet-stream",
            info.model_dump_json().encode(),
            hamlet,
        )

        # Post the hook saying the file is in place
        result = self.client_post(
            "/api/internal/tusd",
            self.request(info).model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 200)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {"url": f"/user_uploads/{path_id}", "filename": "zulip.txt"},
        )
        self.assertEqual(
            result_json["HttpResponse"]["Header"], {"Content-Type": "application/json"}
        )

        attachment = Attachment.objects.get(path_id=path_id)
        self.assertEqual(attachment.size, len("zulip!"))
        self.assertEqual(attachment.content_type, "text/plain")

        # Assert that the .info file is still there -- tusd needs it
        # to verify that the upload completed successfully
        assert settings.LOCAL_FILES_DIR is not None
        self.assertTrue(os.path.exists(os.path.join(settings.LOCAL_FILES_DIR, path_id)))
        self.assertTrue(os.path.exists(os.path.join(settings.LOCAL_FILES_DIR, f"{path_id}.info")))

    def test_no_metadata(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Act like tusd does -- put the file and its .info in place
        path_id = upload_backend.generate_message_upload_path(
            str(hamlet.realm.id), sanitize_name("")
        )
        upload_backend.upload_message_attachment(path_id, "", "ignored", b"zulip!", hamlet)

        info = TusUpload(
            id=path_id,
            size=len("zulip!"),
            offset=0,
            size_is_deferred=False,
            meta_data={},
            is_final=False,
            is_partial=False,
            partial_uploads=None,
            storage=None,
        )
        upload_backend.upload_message_attachment(
            f"{path_id}.info",
            ".info",
            "ignored",
            info.model_dump_json().encode(),
            hamlet,
        )

        # Post the hook saying the file is in place
        result = self.client_post(
            "/api/internal/tusd",
            self.request(info).model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 200)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {"url": f"/user_uploads/{path_id}", "filename": "uploaded-file"},
        )
        self.assertEqual(
            result_json["HttpResponse"]["Header"], {"Content-Type": "application/json"}
        )

        attachment = Attachment.objects.get(path_id=path_id)
        self.assertEqual(attachment.size, len("zulip!"))
        self.assertEqual(attachment.content_type, "application/octet-stream")

        assert settings.LOCAL_FILES_DIR is not None
        self.assertTrue(os.path.exists(os.path.join(settings.LOCAL_FILES_DIR, path_id)))
        self.assertTrue(os.path.exists(os.path.join(settings.LOCAL_FILES_DIR, f"{path_id}.info")))

    @use_s3_backend
    @override_settings(S3_UPLOADS_STORAGE_CLASS="STANDARD_IA")
    def test_s3_upload(self) -> None:
        hamlet = self.example_user("hamlet")
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        upload_backend = S3UploadBackend()
        filename = "some 例 example.png"
        path_id = upload_backend.generate_message_upload_path(
            str(hamlet.realm.id), sanitize_name(filename, strict=True)
        )
        self.assertTrue(path_id.endswith("/some-example.png"))
        info = TusUpload(
            id=path_id,
            size=len("zulip!"),
            offset=0,
            size_is_deferred=False,
            meta_data={
                "filename": filename,
                "filetype": "image/png",
                "name": filename,
                "type": "image/png",
            },
            is_final=False,
            is_partial=False,
            partial_uploads=None,
            storage=None,
        )
        bucket.Object(path_id).put(
            Body=b"zulip!",
            ContentType="application/octet-stream",
            Metadata={k: v.encode("ascii", "replace").decode() for k, v in info.meta_data.items()},
        )
        bucket.Object(f"{path_id}.info").put(
            Body=info.model_dump_json().encode(),
        )

        # Post the hook saying the file is in place
        self.login("hamlet")
        result = self.client_post(
            "/api/internal/tusd",
            self.request(info).model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        result_json = result.json()
        self.assertEqual(result_json["HttpResponse"]["StatusCode"], 200)
        self.assertEqual(
            orjson.loads(result_json["HttpResponse"]["Body"]),
            {"url": f"/user_uploads/{path_id}", "filename": filename},
        )
        self.assertEqual(
            result_json["HttpResponse"]["Header"], {"Content-Type": "application/json"}
        )

        attachment = Attachment.objects.get(path_id=path_id)
        self.assertEqual(attachment.size, len("zulip!"))
        self.assertEqual(attachment.content_type, "image/png")

        assert settings.LOCAL_FILES_DIR is None
        response = bucket.Object(path_id).get()
        self.assertEqual(response["ContentType"], "image/png")
        self.assertEqual(
            response["ContentDisposition"],
            "inline; filename*=utf-8''some%20%E4%BE%8B%20example.png",
        )
        self.assertEqual(response["StorageClass"], "STANDARD_IA")
        self.assertEqual(
            response["Metadata"],
            {"realm_id": str(hamlet.realm_id), "user_profile_id": str(hamlet.id)},
        )

        response = bucket.Object(f"{path_id}.info").get()
        self.assertEqual(response["ContentType"], "binary/octet-stream")


class TusdPreTerminateTest(ZulipTestCase):
    def request(self, info: TusUpload) -> TusHook:
        return TusHook(
            type="pre-terminate",
            event=TusEvent(
                upload=info,
                http_request=TusHTTPRequest(
                    method="PATCH",
                    uri=f"/api/v1/tus/{info.id}",
                    remote_addr="12.34.56.78",
                    header={},
                ),
            ),
        )

    def test_tusd_pre_terminate_hook(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")

        # Act like tusd does -- put the file and its .info in place
        path_id = upload_backend.generate_message_upload_path(
            str(hamlet.realm.id), sanitize_name("zulip.txt")
        )
        upload_backend.upload_message_attachment(
            path_id, "zulip.txt", "text/plain", b"zulip!", hamlet
        )

        info = TusUpload(
            id=path_id,
            size=len("zulip!"),
            offset=0,
            size_is_deferred=False,
            meta_data={
                "filename": "zulip.txt",
                "filetype": "text/plain",
                "name": "zulip.txt",
                "type": "text/plain",
            },
            is_final=False,
            is_partial=False,
            partial_uploads=None,
            storage=None,
        )

        # Try to terminate the upload before it's in Attachments
        result = self.client_post(
            "/api/internal/tusd",
            self.request(info).model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {})

        # Make the attachment
        create_attachment(
            "zulip.txt",
            path_id,
            "text/plain",
            b"zulip!",
            hamlet,
            hamlet.realm,
        )

        # The terminate should get rejected now
        result = self.client_post(
            "/api/internal/tusd",
            self.request(info).model_dump(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"RejectTermination": True})
