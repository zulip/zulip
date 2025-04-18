import os
import re
from datetime import timedelta
from io import StringIO
from unittest import mock
from unittest.mock import patch
from urllib.parse import quote

import orjson
import pyvips
import time_machine
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now as timezone_now
from pyvips import at_least_libvips
from pyvips import version as libvips_version
from typing_extensions import override

import zerver.lib.upload
from analytics.models import RealmCount
from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_create_user
from zerver.actions.message_send import internal_send_private_message
from zerver.actions.realm_icon import do_change_icon_source
from zerver.actions.realm_logo import do_change_logo_source
from zerver.actions.realm_settings import do_change_realm_plan_type, do_set_realm_property
from zerver.actions.user_settings import do_delete_avatar_image
from zerver.lib.attachments import validate_attachment_request
from zerver.lib.avatar import (
    DEFAULT_AVATAR_FILE,
    avatar_url,
    get_avatar_field,
    get_static_avatar_url,
)
from zerver.lib.cache import cache_delete, cache_get, get_realm_used_upload_space_cache_key
from zerver.lib.create_user import copy_default_settings
from zerver.lib.initial_password import initial_password
from zerver.lib.realm_icon import realm_icon_url
from zerver.lib.realm_logo import get_realm_logo_url
from zerver.lib.test_classes import UploadSerializeMixin, ZulipTestCase
from zerver.lib.test_helpers import (
    avatar_disk_path,
    consume_response,
    get_test_image_file,
    ratelimit_rule,
)
from zerver.lib.upload import sanitize_name, upload_message_attachment
from zerver.lib.upload.base import ZulipUploadBackend
from zerver.lib.upload.local import LocalUploadBackend
from zerver.lib.upload.s3 import S3UploadBackend
from zerver.models import Attachment, Message, OnboardingStep, Realm, RealmDomain, UserProfile
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot, get_user_by_delivery_email


class FileUploadTest(UploadSerializeMixin, ZulipTestCase):
    def test_rest_endpoint(self) -> None:
        """
        Tests the /api/v1/user_uploads API endpoint. Here a single file is uploaded
        and downloaded using a username and api_key
        """
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        # Upload file via API
        result = self.api_post(self.example_user("hamlet"), "/api/v1/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)
        self.assertIn("uri", response_dict)
        self.assertIn("url", response_dict)
        url = response_dict["url"]
        self.assertEqual(response_dict["uri"], url)
        base = "/user_uploads/"
        self.assertEqual(base, url[: len(base)])

        # Download file via API
        self.logout()
        response = self.api_get(self.example_user("hamlet"), url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.getvalue(), b"zulip!")

        # Files uploaded through the API should be accessible via the web client
        self.login("hamlet")
        self.assertEqual(self.client_get(url).getvalue(), b"zulip!")

    def test_mobile_api_endpoint(self) -> None:
        """
        Tests the /api/v1/user_uploads API endpoint with ?api_key
        auth. Here a single file is uploaded and downloaded using a
        username and api_key
        """
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        # Upload file via API
        result = self.api_post(self.example_user("hamlet"), "/api/v1/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)
        self.assertIn("uri", response_dict)
        self.assertIn("url", response_dict)
        url = response_dict["url"]
        self.assertEqual(response_dict["uri"], url)
        base = "/user_uploads/"
        self.assertEqual(base, url[: len(base)])

        self.logout()

        # Try to download file via API, passing URL and invalid API key
        user_profile = self.example_user("hamlet")

        response = self.client_get(url, {"api_key": "invalid"})
        self.assertEqual(response.status_code, 401)

        response = self.client_get(url, {"api_key": user_profile.api_key})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.getvalue(), b"zulip!")

    def test_file_too_big_failure(self) -> None:
        """
        Attempting to upload big files should fail.
        """
        self.login("hamlet")
        fp = StringIO("bah!")
        fp.name = "a.txt"

        # Use MAX_FILE_UPLOAD_SIZE of 0, because the next increment
        # would be 1MB.
        with self.settings(MAX_FILE_UPLOAD_SIZE=0):
            result = self.client_post("/json/user_uploads", {"f1": fp})
        self.assert_json_error(
            result,
            "File is larger than this server's configured maximum upload size (0 MiB).",
        )

    def test_file_too_big_failure_standard_plan(self) -> None:
        """
        Verify error message where a plan is involved.
        """
        self.login("hamlet")
        fp = StringIO("bah!")
        fp.name = "a.txt"

        realm = get_realm("zulip")
        realm.plan_type = Realm.PLAN_TYPE_LIMITED
        realm.save()
        with self.settings(MAX_FILE_UPLOAD_SIZE=0):
            result = self.client_post("/json/user_uploads", {"f1": fp})
        self.assert_json_error(
            result,
            "File is larger than the maximum upload size (0 MiB) allowed by your organization's plan.",
        )

    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet")
        fp = StringIO("bah!")
        fp.name = "a.txt"
        fp2 = StringIO("pshaw!")
        fp2.name = "b.txt"

        result = self.client_post("/json/user_uploads", {"f1": fp, "f2": fp2})
        self.assert_json_error(result, "You may only upload one file at a time")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet")

        result = self.client_post("/json/user_uploads")
        self.assert_json_error(result, "You must specify a file to upload")

    def test_guess_content_type_from_filename(self) -> None:
        """
        Test coverage for files without content-type in the metadata;
        in which case we try to guess the content-type from the filename.
        """
        uploaded_file = SimpleUploadedFile("somefile", b"zulip!", content_type="")
        result = self.api_post(
            self.example_user("hamlet"), "/api/v1/user_uploads", {"file": uploaded_file}
        )

        self.login("hamlet")
        response_dict = self.assert_json_success(result)
        url = response_dict["url"]
        result = self.client_get(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Content-Type"], "application/octet-stream")
        consume_response(result)

        uploaded_file = SimpleUploadedFile("somefile.txt", b"zulip!", content_type="")
        result = self.api_post(
            self.example_user("hamlet"), "/api/v1/user_uploads", {"file": uploaded_file}
        )
        self.assert_json_success(result)

        response_dict = self.assert_json_success(result)
        url = response_dict["url"]
        result = self.client_get(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Content-Type"], "text/plain")
        consume_response(result)

    def test_preserve_provided_content_type(self) -> None:
        uploaded_file = SimpleUploadedFile("somefile.txt", b"zulip!", content_type="image/png")
        result = self.api_post(
            self.example_user("hamlet"), "/api/v1/user_uploads", {"file": uploaded_file}
        )

        self.login("hamlet")
        response_dict = self.assert_json_success(result)
        url = response_dict["url"]
        result = self.client_get(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Content-Type"], "image/png")
        consume_response(result)

    # This test will go through the code path for uploading files onto LOCAL storage
    # when Zulip is in DEVELOPMENT mode.
    def test_file_upload_authed(self) -> None:
        """
        A call to /json/user_uploads should return a url and actually create an
        entry in the database. This entry will be marked unclaimed till a message
        refers it.
        """
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)
        self.assertIn("uri", response_dict)
        self.assertIn("url", response_dict)
        url = response_dict["url"]
        self.assertEqual(response_dict["uri"], url)
        base = "/user_uploads/"
        self.assertEqual(base, url[: len(base)])

        self.assertEqual(self.client_get(url).getvalue(), b"zulip!")

        # Check the download endpoint
        download_url = url.replace("/user_uploads/", "/user_uploads/download/")
        result = self.client_get(download_url)
        self.assertEqual(result.getvalue(), b"zulip!")
        self.assertIn("attachment;", result.headers["Content-Disposition"])

        # check if DB has attachment marked as unclaimed
        entry = Attachment.objects.get(file_name="zulip.txt")
        self.assertEqual(entry.is_claimed(), False)

        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        body = f"First message ...[zulip.txt]({hamlet.realm.host}{url})"
        self.send_stream_message(hamlet, "Denmark", body, "test")

        # Now try the endpoint that's supposed to return a temporary URL for access
        # to the file.
        result = self.client_get("/json" + url)
        data = self.assert_json_success(result)
        url_only_url = data["url"]
        # Ensure this is different from the original url:
        self.assertNotEqual(url_only_url, url)
        self.assertIn("user_uploads/temporary/", url_only_url)
        self.assertTrue(url_only_url.endswith("zulip.txt"))
        # The generated URL has a token authorizing the requester to access the file
        # without being logged in.
        self.logout()
        self.assertEqual(self.client_get(url_only_url).getvalue(), b"zulip!")
        # The original url shouldn't work when logged out -- it redirects to the login page
        result = self.client_get(url)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.headers["Location"].endswith(f"/login/?next={url}"))

    def test_serve_file_unauthed(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip_web_public.txt"

        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]

        with ratelimit_rule(86400, 1000, domain="spectator_attachment_access_by_file"):
            # Deny file access for non-web-public stream
            self.subscribe(self.example_user("hamlet"), "Denmark")
            host = self.example_user("hamlet").realm.host
            body = f"First message ...[zulip.txt](http://{host}" + url + ")"
            self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test")

            self.logout()
            response = self.client_get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith(f"/login/?next={url}"))

            # Allow file access for web-public stream
            self.login("hamlet")
            self.make_stream("web-public-stream", is_web_public=True)
            self.subscribe(self.example_user("hamlet"), "web-public-stream")
            body = f"First message ...[zulip.txt](http://{host}" + url + ")"
            self.send_stream_message(self.example_user("hamlet"), "web-public-stream", body, "test")

            self.logout()
            response = self.client_get(url)
            self.assertEqual(response.status_code, 200)
            consume_response(response)

        # Deny file access since rate limited
        with ratelimit_rule(86400, 0, domain="spectator_attachment_access_by_file"):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith(f"/login/?next={url}"))

        # Check that the /download/ variant works as well
        download_url = url.replace("/user_uploads/", "/user_uploads/download/")
        with ratelimit_rule(86400, 1000, domain="spectator_attachment_access_by_file"):
            response = self.client_get(download_url)
            self.assertEqual(response.status_code, 200)
            consume_response(response)
        with ratelimit_rule(86400, 0, domain="spectator_attachment_access_by_file"):
            response = self.client_get(download_url)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith(f"/login/?next={download_url}"))

        # Deny random file access
        response = self.client_get(
            "/user_uploads/2/71/QYB7LA-ULMYEad-QfLMxmI2e/zulip-non-existent.txt"
        )
        self.assertEqual(response.status_code, 404)

    def test_serve_local_file_unauthed_invalid_token(self) -> None:
        result = self.client_get("/user_uploads/temporary/badtoken/file.png")
        self.assert_json_error(result, "Invalid token")

    def test_serve_local_file_unauthed_altered_filename(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)
        url = "/json" + response_dict["url"]

        result = self.client_get(url)
        data = self.assert_json_success(result)
        url_only_url = data["url"]

        self.assertTrue(url_only_url.endswith("zulip.txt"))
        url_only_url_changed_filename = url_only_url.split("zulip.txt")[0] + "differentname.exe"
        result = self.client_get(url_only_url_changed_filename)
        self.assert_json_error(result, "Invalid filename")

    def test_serve_local_file_unauthed_token_expires(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        now = timezone_now()
        with time_machine.travel(now, tick=False):
            result = self.client_post("/json/user_uploads", {"file": fp})
            response_dict = self.assert_json_success(result)
            url = "/json" + response_dict["url"]

            result = self.client_get(url)
            data = self.assert_json_success(result)
            url_only_url = data["url"]
            self.logout()
            self.assertEqual(self.client_get(url_only_url).getvalue(), b"zulip!")

        with time_machine.travel(now + timedelta(seconds=30), tick=False):
            self.assertEqual(self.client_get(url_only_url).getvalue(), b"zulip!")

        # After over 60 seconds, the token should become invalid:
        with time_machine.travel(now + timedelta(seconds=61), tick=False):
            result = self.client_get(url_only_url)
            self.assert_json_error(result, "Invalid token")

    def test_serve_local_file_unauthed_token_deleted(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        now = timezone_now()
        with time_machine.travel(now, tick=False):
            result = self.client_post("/json/user_uploads", {"file": fp})
            response_dict = self.assert_json_success(result)
            url = "/json" + response_dict["url"]

            result = self.client_get(url)
            data = self.assert_json_success(result)
            url_only_url = data["url"]

            path_id = response_dict["url"].removeprefix("/user_uploads/")
            Attachment.objects.get(path_id=path_id).delete()

            result = self.client_get(url_only_url)
            self.assert_json_error(result, "Invalid token")

    def test_file_download_unauthed(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)
        url = response_dict["url"]

        self.logout()
        response = self.client_get(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(f"/login/?next={url}"))

    def test_image_download_unauthed(self) -> None:
        """
        As the above, but with an Accept header that prefers images.
        """
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)
        url = response_dict["url"]

        self.logout()
        response = self.client_get(
            url,
            # This is what Chrome sends for <img> tags
            headers={"Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.headers["Content-Type"], "image/png")
        consume_response(response)

    def test_removed_file_download(self) -> None:
        """
        Trying to download deleted files should return 404 error
        """
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)

        assert settings.LOCAL_UPLOADS_DIR is not None
        self.rm_tree(settings.LOCAL_UPLOADS_DIR)

        response = self.client_get(response_dict["uri"])
        self.assertEqual(response.status_code, 404)
        response = self.client_get(response_dict["url"])
        self.assertEqual(response.status_code, 404)

    def test_non_existing_file_download(self) -> None:
        """
        Trying to download a file that was never uploaded will return a json_error
        """
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        response = self.client_get(
            f"http://{hamlet.realm.host}/user_uploads/{hamlet.realm_id}/ff/gg/abc.py"
        )
        self.assertEqual(response.status_code, 404)
        self.assert_in_response("This file does not exist or has been deleted.", response)

    def test_non_existing_image_download(self) -> None:
        """
        As the above method, but with an Accept header that prefers images to text
        """
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        response = self.client_get(
            f"http://{hamlet.realm.host}/user_uploads/{hamlet.realm_id}/ff/gg/abc.png",
            # This is what Chrome sends for <img> tags
            headers={"Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "image/png")
        consume_response(response)

        response = self.client_get(
            f"http://{hamlet.realm.host}/user_uploads/{hamlet.realm_id}/ff/gg/abc.png",
            # Ask for something neither image nor text -- you get text as a default
            headers={"Accept": "audio/*,application/octet-stream"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")
        self.assert_in_response("This file does not exist or has been deleted.", response)

    def test_attachment_url_without_upload(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        with self.assertLogs(level="WARNING") as warn_log:
            body = f"Test message ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/{hamlet.realm_id}/64/fake_path_id.txt)"
            message_id = self.send_stream_message(
                self.example_user("hamlet"), "Denmark", body, "test"
            )
        self.assertFalse(
            Attachment.objects.filter(path_id=f"{hamlet.realm_id}/64/fake_path_id.txt").exists()
        )

        self.assertEqual(
            warn_log.output,
            [
                f"WARNING:root:User {hamlet.id} tried to share upload {hamlet.realm_id}/64/fake_path_id.txt in message {message_id}, but lacks permission"
            ],
        )

    def test_multiple_claim_attachments(self) -> None:
        """
        This test tries to claim the same attachment twice. The messages field in
        the Attachment model should have both the messages in its entry.
        """
        self.login("hamlet")
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {"file": d1})
        response_dict = self.assert_json_success(result)
        d1_path_id = re.sub(r"/user_uploads/", "", response_dict["url"])

        self.subscribe(self.example_user("hamlet"), "Denmark")
        host = self.example_user("hamlet").realm.host
        body = f"First message ...[zulip.txt](http://{host}/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test")
        body = f"Second message ...[zulip.txt](http://{host}/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test")

        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)

    def test_multiple_claim_attachments_different_owners(self) -> None:
        """This test tries to claim the same attachment more than once, first
        with a private stream and then with different recipients."""
        self.login("hamlet")
        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {"file": d1})
        response_dict = self.assert_json_success(result)
        d1_path_id = re.sub(r"/user_uploads/", "", response_dict["url"])
        host = self.example_user("hamlet").realm.host

        self.make_stream("private_stream", invite_only=True)
        self.subscribe(self.example_user("hamlet"), "private_stream")

        # First, send the message to the new private stream.
        body = f"First message ...[zulip.txt](http://{host}/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_user("hamlet"), "private_stream", body, "test")
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 1)

        # Then, try having a user who didn't receive the message try to publish it, and fail
        body = f"Illegal message ...[zulip.txt](http://{host}/user_uploads/" + d1_path_id + ")"
        cordelia = self.example_user("cordelia")
        with self.assertLogs(level="WARNING") as warn_log:
            self.send_stream_message(cordelia, "Verona", body, "test")
        self.assertTrue(
            f"WARNING:root:User {cordelia.id} tried to share upload" in warn_log.output[0]
            and "but lacks permission" in warn_log.output[0]
        )
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 1)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_web_public)

        # Then, have it in a direct message to another user, giving that other user access.
        body = f"Second message ...[zulip.txt](http://{host}/user_uploads/" + d1_path_id + ")"
        self.send_personal_message(self.example_user("hamlet"), self.example_user("othello"), body)
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 2)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_realm_public)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_web_public)

        # Then, have that new recipient user publish it.
        body = f"Third message ...[zulip.txt](http://{host}/user_uploads/" + d1_path_id + ")"
        self.send_stream_message(self.example_user("othello"), "Verona", body, "test")
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 3)
        self.assertTrue(Attachment.objects.get(path_id=d1_path_id).is_realm_public)
        self.assertFalse(Attachment.objects.get(path_id=d1_path_id).is_web_public)

        # Finally send to Rome, the web-public stream, and confirm it's now web-public
        body = f"Fourth message ...[zulip.txt](http://{host}/user_uploads/" + d1_path_id + ")"
        self.subscribe(self.example_user("othello"), "Rome")
        self.send_stream_message(self.example_user("othello"), "Rome", body, "test")
        self.assertEqual(Attachment.objects.get(path_id=d1_path_id).messages.count(), 4)
        self.assertTrue(Attachment.objects.get(path_id=d1_path_id).is_realm_public)
        self.assertTrue(Attachment.objects.get(path_id=d1_path_id).is_web_public)

    def test_check_attachment_reference_update(self) -> None:
        f1 = StringIO("file1")
        f1.name = "file1.txt"
        f2 = StringIO("file2")
        f2.name = "file2.txt"
        f3 = StringIO("file3")
        f3.name = "file3.txt"
        hamlet = self.example_user("hamlet")
        host = hamlet.realm.host

        self.login_user(hamlet)
        result = self.client_post("/json/user_uploads", {"file": f1})
        response_dict = self.assert_json_success(result)
        f1_path_id = re.sub(r"/user_uploads/", "", response_dict["url"])

        result = self.client_post("/json/user_uploads", {"file": f2})
        response_dict = self.assert_json_success(result)
        f2_path_id = re.sub(r"/user_uploads/", "", response_dict["url"])

        self.subscribe(hamlet, "test")
        body = (
            f"[f1.txt](http://{host}/user_uploads/" + f1_path_id + ") "
            f"[f2.txt](http://{host}/user_uploads/" + f2_path_id + ")"
        )
        msg_id = self.send_stream_message(hamlet, "test", body, "test")

        result = self.client_post("/json/user_uploads", {"file": f3})
        response_dict = self.assert_json_success(result)
        f3_path_id = re.sub(r"/user_uploads/", "", response_dict["url"])

        new_body = (
            f"[f3.txt](http://{host}/user_uploads/" + f3_path_id + ") "
            f"[f2.txt](http://{host}/user_uploads/" + f2_path_id + ")"
        )
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": new_body,
            },
        )
        self.assert_json_success(result)

        message = Message.objects.get(id=msg_id)
        f1_attachment = Attachment.objects.get(path_id=f1_path_id)
        f2_attachment = Attachment.objects.get(path_id=f2_path_id)
        f3_attachment = Attachment.objects.get(path_id=f3_path_id)

        self.assertTrue(message not in f1_attachment.messages.all())
        self.assertTrue(message in f2_attachment.messages.all())
        self.assertTrue(message in f3_attachment.messages.all())

        # Delete all the attachments from the message
        new_body = "(deleted)"
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "content": new_body,
            },
        )
        self.assert_json_success(result)

        message = Message.objects.get(id=msg_id)
        f1_attachment = Attachment.objects.get(path_id=f1_path_id)
        f2_attachment = Attachment.objects.get(path_id=f2_path_id)
        f3_attachment = Attachment.objects.get(path_id=f3_path_id)
        self.assertTrue(message not in f1_attachment.messages.all())
        self.assertTrue(message not in f2_attachment.messages.all())
        self.assertTrue(message not in f3_attachment.messages.all())

    def test_file_name(self) -> None:
        """
        Unicode filenames should be processed correctly.
        """
        self.login("hamlet")
        for expected in ["Здравейте.txt", "test"]:
            fp = StringIO("bah!")
            fp.name = quote(expected)

            result = self.client_post("/json/user_uploads", {"f1": fp})
            response_dict = self.assert_json_success(result)
            assert sanitize_name(expected) in response_dict["uri"]
            assert sanitize_name(expected) in response_dict["url"]

    def test_sanitize_file_name(self) -> None:
        self.login("hamlet")
        for uploaded_filename, expected_url, expected_filename in [
            ("../foo", "foo", "foo"),
            (".. ", "uploaded-file", ".. "),
            ("/", "f1", "f1"),
            ("./", "f1", "f1"),
            ("././", "f1", "f1"),
            (".!", "uploaded-file", ".!"),
            ("**", "uploaded-file", "**"),
            ("foo bar--baz", "foo-bar-baz", "foo bar--baz"),
        ]:
            fp = StringIO("bah!")
            fp.name = quote(uploaded_filename)

            result = self.client_post("/json/user_uploads", {"f1": fp})
            response_dict = self.assert_json_success(result)
            self.assertNotIn(response_dict["uri"], uploaded_filename)
            self.assertTrue(response_dict["uri"].endswith("/" + expected_url))
            self.assertNotIn(response_dict["url"], uploaded_filename)
            self.assertTrue(response_dict["url"].endswith("/" + expected_url))
            self.assertEqual(response_dict["filename"], expected_filename)

    def test_realm_quota(self) -> None:
        """
        Realm quota for uploading should not be exceeded.
        """
        self.login("hamlet")

        d1 = StringIO("zulip!")
        d1.name = "dummy_1.txt"
        result = self.client_post("/json/user_uploads", {"file": d1})
        response_dict = self.assert_json_success(result)
        d1_path_id = re.sub(r"/user_uploads/", "", response_dict["url"])
        d1_attachment = Attachment.objects.get(path_id=d1_path_id)

        realm = get_realm("zulip")
        realm.custom_upload_quota_gb = 1
        realm.save(update_fields=["custom_upload_quota_gb"])

        # The size of StringIO("zulip!") is 6 bytes. Setting the size of
        # d1_attachment to realm.upload_quota_bytes() - 11 should allow
        # us to upload only one more attachment.
        quota = realm.upload_quota_bytes()
        assert quota is not None
        d1_attachment.size = quota - 11
        d1_attachment.save(update_fields=["size"])

        d2 = StringIO("zulip!")
        d2.name = "dummy_2.txt"
        result = self.client_post("/json/user_uploads", {"file": d2})
        self.assert_json_success(result)

        d3 = StringIO("zulip!")
        d3.name = "dummy_3.txt"
        result = self.client_post("/json/user_uploads", {"file": d3})
        self.assert_json_error(result, "Upload would exceed your organization's upload quota.")

        realm.custom_upload_quota_gb = None
        realm.save(update_fields=["custom_upload_quota_gb"])
        result = self.client_post("/json/user_uploads", {"file": d3})
        self.assert_json_success(result)

    def test_cross_realm_file_access(self) -> None:
        def create_user(email: str, realm_id: str) -> UserProfile:
            password = initial_password(email)
            if password is not None:
                self.register(email, password, subdomain=realm_id)
                # self.register has the side-effect of ending up with a logged in session
                # for the new user. We don't want that in these tests.
                self.logout()
            return get_user_by_delivery_email(email, get_realm(realm_id))

        test_subdomain = "uploadtest.example.com"
        user1_email = "user1@uploadtest.example.com"
        user2_email = "test-og-bot@zulip.com"
        user3_email = "other-user@uploadtest.example.com"

        r1 = do_create_realm(string_id=test_subdomain, name=test_subdomain)
        do_set_realm_property(r1, "invite_required", False, acting_user=None)
        RealmDomain.objects.create(realm=r1, domain=test_subdomain)

        user_1 = create_user(user1_email, test_subdomain)
        user_2 = create_user(user2_email, "zulip")
        user_3 = create_user(user3_email, test_subdomain)
        host = user_3.realm.host

        # Send a message from @zulip.com -> @uploadtest.example.com
        self.login_user(user_2)
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]
        fp_path_id = re.sub(r"/user_uploads/", "", url)
        body = f"First message ...[zulip.txt](http://{host}/user_uploads/" + fp_path_id + ")"
        with self.settings(CROSS_REALM_BOT_EMAILS={user_2.email, user_3.email}):
            internal_send_private_message(
                sender=get_system_bot(user_2.email, user_2.realm_id),
                recipient_user=user_1,
                content=body,
            )

        self.login_user(user_1)
        response = self.client_get(url, subdomain=test_subdomain)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.getvalue(), b"zulip!")
        self.logout()

        # Confirm other cross-realm users can't read it.
        self.login_user(user_3)
        response = self.client_get(url, subdomain=test_subdomain)
        self.assertEqual(response.status_code, 403)
        self.assert_in_response("You are not authorized to view this file.", response)

        # Verify that cross-realm access to files for spectators is denied.
        self.logout()
        response = self.client_get(url, subdomain=test_subdomain)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(f"/login/?next={url}"))

    def test_file_download_authorization_invite_only(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        realm = hamlet.realm
        subscribed_users = [hamlet, cordelia]
        unsubscribed_users = [self.example_user("othello"), self.example_user("prospero")]
        stream_name = "test-subscribe"
        self.make_stream(
            stream_name, realm=realm, invite_only=True, history_public_to_subscribers=False
        )

        for subscribed_user in subscribed_users:
            self.subscribe(subscribed_user, stream_name)

        self.login_user(hamlet)
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]
        fp_path_id = re.sub(r"/user_uploads/", "", url)
        body = f"First message ...[zulip.txt](http://{realm.host}/user_uploads/" + fp_path_id + ")"
        self.send_stream_message(hamlet, stream_name, body, "test")
        self.logout()

        # Owner user should be able to view file
        self.login_user(hamlet)
        with self.assert_database_query_count(5):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.getvalue(), b"zulip!")
        self.logout()

        # Subscribed user who received the message should be able to view file
        self.login_user(cordelia)
        with self.assert_database_query_count(8):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.getvalue(), b"zulip!")
        self.logout()

        def assert_cannot_access_file(user: UserProfile) -> None:
            response = self.api_get(user, url)
            self.assertEqual(response.status_code, 403)
            self.assert_in_response("You are not authorized to view this file.", response)

        late_subscribed_user = self.example_user("aaron")
        self.subscribe(late_subscribed_user, stream_name)
        assert_cannot_access_file(late_subscribed_user)

        # Unsubscribed user should not be able to view file
        for unsubscribed_user in unsubscribed_users:
            assert_cannot_access_file(unsubscribed_user)

    def test_file_download_authorization_invite_only_with_shared_history(self) -> None:
        user = self.example_user("hamlet")
        polonius = self.example_user("polonius")
        subscribed_users = [user, polonius]
        unsubscribed_users = [self.example_user("othello"), self.example_user("prospero")]
        stream_name = "test-subscribe"
        self.make_stream(
            stream_name, realm=user.realm, invite_only=True, history_public_to_subscribers=True
        )

        for subscribed_user in subscribed_users:
            self.subscribe(subscribed_user, stream_name)

        self.login_user(user)
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]
        fp_path_id = re.sub(r"/user_uploads/", "", url)
        body = (
            f"First message ...[zulip.txt](http://{user.realm.host}/user_uploads/"
            + fp_path_id
            + ")"
        )
        self.send_stream_message(user, stream_name, body, "test")
        self.logout()

        # Add aaron as a subscribed after the message was sent
        late_subscribed_user = self.example_user("aaron")
        self.subscribe(late_subscribed_user, stream_name)
        subscribed_users.append(late_subscribed_user)

        # Owner user should be able to view file
        self.login_user(user)
        with self.assert_database_query_count(5):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.getvalue(), b"zulip!")
        self.logout()

        # Originally subscribed user should be able to view file
        self.login_user(polonius)
        with self.assert_database_query_count(8):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.getvalue(), b"zulip!")
        self.logout()

        # Subscribed user who did not receive the message should also be able to view file
        self.login_user(late_subscribed_user)
        with self.assert_database_query_count(9):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.getvalue(), b"zulip!")
        self.logout()
        # It takes a few extra queries to verify access because of shared history.

        def assert_cannot_access_file(user: UserProfile) -> None:
            self.login_user(user)
            # It takes a few extra queries to verify lack of access with shared history.
            with self.assert_database_query_count(10):
                response = self.client_get(url)
            self.assertEqual(response.status_code, 403)
            self.assert_in_response("You are not authorized to view this file.", response)
            self.logout()

        # Unsubscribed user should not be able to view file
        for unsubscribed_user in unsubscribed_users:
            assert_cannot_access_file(unsubscribed_user)

    def test_multiple_message_attachment_file_download(self) -> None:
        hamlet = self.example_user("hamlet")
        for i in range(5):
            stream_name = f"test-subscribe {i}"
            self.make_stream(
                stream_name,
                realm=hamlet.realm,
                invite_only=True,
                history_public_to_subscribers=True,
            )
            self.subscribe(hamlet, stream_name)

        self.login_user(hamlet)
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]
        fp_path_id = re.sub(r"/user_uploads/", "", url)
        for i in range(20):
            body = (
                f"First message ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/"
                + fp_path_id
                + ")"
            )
            self.send_stream_message(
                self.example_user("hamlet"), f"test-subscribe {i % 5}", body, "test"
            )
        self.logout()

        user = self.example_user("aaron")
        self.login_user(user)
        with self.assert_database_query_count(10):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 403)
            self.assert_in_response("You are not authorized to view this file.", response)

        self.subscribe(user, "test-subscribe 1")
        self.subscribe(user, "test-subscribe 2")

        # If we were accidentally one query per message, this would be 20+
        with self.assert_database_query_count(9):
            response = self.client_get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.getvalue(), b"zulip!")

        with self.assert_database_query_count(5):
            self.assertTrue(validate_attachment_request(user, fp_path_id)[0])

        self.logout()

    def test_file_download_authorization_public(self) -> None:
        subscribed_users = [self.example_user("hamlet"), self.example_user("iago")]
        unsubscribed_users = [self.example_user("othello"), self.example_user("prospero")]
        realm = get_realm("zulip")
        for subscribed_user in subscribed_users:
            self.subscribe(subscribed_user, "test-subscribe")

        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]
        fp_path_id = re.sub(r"/user_uploads/", "", url)
        body = f"First message ...[zulip.txt](http://{realm.host}/user_uploads/" + fp_path_id + ")"
        self.send_stream_message(self.example_user("hamlet"), "test-subscribe", body, "test")
        self.logout()

        # Now all users should be able to access the files
        for user in subscribed_users + unsubscribed_users:
            self.login_user(user)
            response = self.client_get(url)
            self.assertEqual(response.getvalue(), b"zulip!")
            self.logout()

    def test_serve_local(self) -> None:
        def check_xsend_links(
            name: str,
            name_str_for_test: str,
            content_disposition: str = "",
            download: bool = False,
            returned_attachment: bool = False,
        ) -> None:
            self.login("hamlet")
            fp = StringIO("zulip!")
            fp.name = name
            result = self.client_post("/json/user_uploads", {"file": fp})
            url = self.assert_json_success(result)["url"]
            fp_path_id = re.sub(r"/user_uploads/", "", url)
            fp_path = os.path.split(fp_path_id)[0]
            if download:
                url = url.replace("/user_uploads/", "/user_uploads/download/")
            with self.settings(DEVELOPMENT=False):
                response = self.client_get(url)
            assert settings.LOCAL_UPLOADS_DIR is not None
            test_run, worker = os.path.split(os.path.dirname(settings.LOCAL_UPLOADS_DIR))
            self.assertEqual(
                response["X-Accel-Redirect"],
                "/internal/local/uploads/" + fp_path + "/" + name_str_for_test,
            )
            if returned_attachment:
                self.assertIn("attachment;", response["Content-disposition"])
            else:
                self.assertIn("inline;", response["Content-disposition"])
            if content_disposition != "":
                self.assertIn(content_disposition, response["Content-disposition"])
            self.assertEqual(set(response["Cache-Control"].split(", ")), {"private", "immutable"})

        check_xsend_links("zulip.txt", "zulip.txt", 'filename="zulip.txt"')
        check_xsend_links(
            "áéБД.txt",
            "%C3%A1%C3%A9%D0%91%D0%94.txt",
            "filename*=utf-8''%C3%A1%C3%A9%D0%91%D0%94.txt",
        )
        check_xsend_links(
            "zulip.html",
            "zulip.html",
            'filename="zulip.html"',
            returned_attachment=True,
        )
        check_xsend_links(
            "zulip.sh",
            "zulip.sh",
            'filename="zulip.sh"',
            returned_attachment=True,
        )
        check_xsend_links(
            "zulip.jpeg",
            "zulip.jpeg",
            'filename="zulip.jpeg"',
            returned_attachment=False,
        )
        check_xsend_links(
            "zulip.jpeg",
            "zulip.jpeg",
            download=True,
            content_disposition='filename="zulip.jpeg"',
            returned_attachment=True,
        )
        check_xsend_links(
            "áéБД.pdf",
            "%C3%A1%C3%A9%D0%91%D0%94.pdf",
            "filename*=utf-8''%C3%A1%C3%A9%D0%91%D0%94.pdf",
            returned_attachment=False,
        )
        check_xsend_links(
            "some file (with spaces).png",
            "some-file-with-spaces.png",
            'filename="some file (with spaces).png"',
            returned_attachment=False,
        )
        check_xsend_links(
            "some file (with spaces).png",
            "some-file-with-spaces.png",
            'filename="some file (with spaces).png"',
            download=True,
            returned_attachment=True,
        )
        check_xsend_links(
            ".().",
            "uploaded-file",
            'filename=".()."',
            returned_attachment=True,
        )
        check_xsend_links("zulip", "zulip", 'filename="zulip"', returned_attachment=True)


class AvatarTest(UploadSerializeMixin, ZulipTestCase):
    def test_get_avatar_field(self) -> None:
        with self.settings(AVATAR_SALT="salt"):
            url = get_avatar_field(
                user_id=17,
                realm_id=5,
                email="foo@example.com",
                avatar_source=UserProfile.AVATAR_FROM_USER,
                avatar_version=2,
                medium=True,
                client_gravatar=False,
            )

        self.assertEqual(
            url,
            "/user_avatars/5/ff062b0fee41738b38c4312bb33bdf3fe2aad463-medium.png",
        )

        url = get_avatar_field(
            user_id=9999,
            realm_id=9999,
            email="foo@example.com",
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            avatar_version=2,
            medium=True,
            client_gravatar=False,
        )

        self.assertEqual(
            url,
            "https://secure.gravatar.com/avatar/b48def645758b95537d4424c84d1a9ff?d=identicon&s=500&version=2",
        )

        url = get_avatar_field(
            user_id=9999,
            realm_id=9999,
            email="foo@example.com",
            avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
            avatar_version=2,
            medium=True,
            client_gravatar=True,
        )

        self.assertEqual(url, None)

    def test_avatar_url(self) -> None:
        """Verifies URL schemes for avatars and realm icons."""
        backend: ZulipUploadBackend = LocalUploadBackend()
        self.assertEqual(backend.get_public_upload_root_url(), "/user_avatars/")
        self.assertEqual(backend.get_avatar_url("hash", False), "/user_avatars/hash.png")
        self.assertEqual(backend.get_avatar_url("hash", True), "/user_avatars/hash-medium.png")
        self.assertEqual(
            backend.get_realm_icon_url(15, 1), "/user_avatars/15/realm/icon.png?version=1"
        )
        self.assertEqual(
            backend.get_realm_logo_url(15, 1, False), "/user_avatars/15/realm/logo.png?version=1"
        )
        self.assertEqual(
            backend.get_realm_logo_url(15, 1, True),
            "/user_avatars/15/realm/night_logo.png?version=1",
        )

        with self.settings(S3_AVATAR_BUCKET="bucket"):
            backend = S3UploadBackend()
            self.assertEqual(
                backend.get_avatar_url("hash", False), "https://bucket.s3.amazonaws.com/hash.png"
            )
            self.assertEqual(
                backend.get_avatar_url("hash", True),
                "https://bucket.s3.amazonaws.com/hash-medium.png",
            )
            self.assertEqual(
                backend.get_realm_icon_url(15, 1),
                "https://bucket.s3.amazonaws.com/15/realm/icon.png?version=1",
            )
            self.assertEqual(
                backend.get_realm_logo_url(15, 1, False),
                "https://bucket.s3.amazonaws.com/15/realm/logo.png?version=1",
            )
            self.assertEqual(
                backend.get_realm_logo_url(15, 1, True),
                "https://bucket.s3.amazonaws.com/15/realm/night_logo.png?version=1",
            )

    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet")
        with get_test_image_file("img.png") as fp1, get_test_image_file("img.png") as fp2:
            result = self.client_post("/json/users/me/avatar", {"f1": fp1, "f2": fp2})
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet")

        result = self.client_post("/json/users/me/avatar")
        self.assert_json_error(result, "You must upload exactly one avatar.")

    def test_avatar_changes_disabled_failure(self) -> None:
        """
        Attempting to upload avatar on a realm with avatar changes disabled should fail.
        """
        self.login("cordelia")
        do_set_realm_property(
            self.example_user("cordelia").realm,
            "avatar_changes_disabled",
            True,
            acting_user=None,
        )

        with get_test_image_file("img.png") as fp1:
            result = self.client_post("/json/users/me/avatar", {"f1": fp1})
        self.assert_json_error(result, "Avatar changes are disabled in this organization.")

    correct_files = [
        ("img.png", "png_resized.png"),
        ("img.jpg", None),  # jpeg resizing is platform-dependent
        ("img.gif", "gif_resized.png"),
        ("img.tif", "tif_resized.png"),
        ("cmyk.jpg", None),
    ]

    def test_get_gravatar_avatar(self) -> None:
        self.login("hamlet")
        cordelia = self.example_user("cordelia")
        cordelia.email = cordelia.delivery_email
        cordelia.save()

        cordelia.avatar_source = UserProfile.AVATAR_FROM_GRAVATAR
        cordelia.save()
        with self.settings(ENABLE_GRAVATAR=True):
            response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertEqual(redirect_url, str(avatar_url(cordelia)) + "&foo=bar")

        with self.settings(
            ENABLE_GRAVATAR=False, GRAVATAR_REALM_OVERRIDE={get_realm("zulip").id: True}
        ):
            response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue("gravatar" in redirect_url)

        with self.settings(ENABLE_GRAVATAR=False):
            response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + "&foo=bar"))

        with self.settings(
            ENABLE_GRAVATAR=True, GRAVATAR_REALM_OVERRIDE={get_realm("zulip").id: False}
        ):
            response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue("gravatar" not in redirect_url)

    def test_get_settings_avatar(self) -> None:
        self.login("hamlet")
        cordelia = self.example_user("cordelia")
        cordelia.email = cordelia.delivery_email
        cordelia.save()
        with self.settings(
            ENABLE_GRAVATAR=False, DEFAULT_AVATAR_URI="http://other.server/avatar.svg"
        ):
            response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertEqual(redirect_url, "http://other.server/avatar.svg?version=1&foo=bar")

    def test_get_user_avatar(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        cordelia.email = cordelia.delivery_email
        cordelia.save()

        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        cross_realm_bot = get_system_bot(settings.WELCOME_BOT, internal_realm.id)

        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()
        response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + "?foo=bar"))

        response = self.client_get(f"/avatar/{cordelia.id}", {"foo": "bar"})
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + "?foo=bar"))

        response = self.client_get("/avatar/")
        self.assertEqual(response.status_code, 404)

        self.logout()

        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            # Test /avatar/<email_or_id> endpoint with HTTP basic auth.
            response = self.api_get(hamlet, "/avatar/cordelia@zulip.com", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + "?foo=bar"))

            response = self.api_get(hamlet, f"/avatar/{cordelia.id}", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia)) + "?foo=bar"))

            # Test cross_realm_bot avatar access using email.
            response = self.api_get(hamlet, "/avatar/welcome-bot@zulip.com", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(str(avatar_url(cross_realm_bot)) + "?foo=bar"))

            # Test cross_realm_bot avatar access using id.
            response = self.api_get(hamlet, f"/avatar/{cross_realm_bot.id}", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(str(avatar_url(cross_realm_bot)) + "?foo=bar"))

            # Without spectators enabled, no unauthenticated access.
            response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
            self.assert_json_error(
                response,
                "Not logged in: API authentication or user session required",
                status_code=401,
            )
            # Disallow access by id for spectators with unauthenticated access
            # when realm public streams is false.
            response = self.client_get(f"/avatar/{cordelia.id}", {"foo": "bar"})
            self.assert_json_error(
                response,
                "Not logged in: API authentication or user session required",
                status_code=401,
            )

        # Allow unauthenticated/spectator requests by ID.
        response = self.client_get(f"/avatar/{cordelia.id}", {"foo": "bar"})
        self.assertEqual(302, response.status_code)

        # Disallow unauthenticated/spectator requests by email.
        response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
        self.assert_json_error(
            response,
            "Not logged in: API authentication or user session required",
            status_code=401,
        )

        self.set_up_db_for_testing_user_access()
        self.login("polonius")

        response = self.client_get(f"/avatar/{cordelia.id}", {"foo": "bar"})
        self.assertEqual(302, response.status_code)
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith("images/unknown-user-avatar.png?foo=bar"))

        response = self.client_get("/avatar/cordelia@zulip.com", {"foo": "bar"})
        self.assertEqual(302, response.status_code)
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith("images/unknown-user-avatar.png?foo=bar"))

        invalid_user_id = 999
        response = self.client_get(f"/avatar/{invalid_user_id}", {"foo": "bar"})
        self.assertEqual(302, response.status_code)
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith("images/unknown-user-avatar.png?foo=bar"))

    def test_get_user_avatar_medium(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        cordelia.email = cordelia.delivery_email
        cordelia.save()

        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()
        response = self.client_get("/avatar/cordelia@zulip.com/medium", {"foo": "bar"})
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + "?foo=bar"))

        response = self.client_get(f"/avatar/{cordelia.id}/medium", {"foo": "bar"})
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + "?foo=bar"))

        self.logout()

        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            # Test /avatar/<email_or_id>/medium endpoint with HTTP basic auth.
            response = self.api_get(hamlet, "/avatar/cordelia@zulip.com/medium", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + "?foo=bar"))

            response = self.api_get(hamlet, f"/avatar/{cordelia.id}/medium", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(str(avatar_url(cordelia, True)) + "?foo=bar"))

            # Without spectators enabled, no unauthenticated access.
            response = self.client_get("/avatar/cordelia@zulip.com/medium", {"foo": "bar"})
            self.assert_json_error(
                response,
                "Not logged in: API authentication or user session required",
                status_code=401,
            )

        # Allow unauthenticated/spectator requests by ID.
        response = self.client_get(f"/avatar/{cordelia.id}/medium", {"foo": "bar"})
        self.assertEqual(302, response.status_code)

        # Disallow unauthenticated/spectator requests by email.
        response = self.client_get("/avatar/cordelia@zulip.com/medium", {"foo": "bar"})
        self.assert_json_error(
            response,
            "Not logged in: API authentication or user session required",
            status_code=401,
        )

        # Allow unauthenticated/spectator requests by ID for a reasonable number of requests.
        with ratelimit_rule(86400, 1000, domain="spectator_attachment_access_by_file"):
            response = self.client_get(f"/avatar/{cordelia.id}/medium", {"foo": "bar"})
            self.assertEqual(302, response.status_code)

        # Deny file access since rate limited
        with ratelimit_rule(86400, 0, domain="spectator_attachment_access_by_file"):
            response = self.client_get(f"/avatar/{cordelia.id}/medium", {"foo": "bar"})
            self.assertEqual(429, response.status_code)

    def test_non_valid_user_avatar(self) -> None:
        # It's debatable whether we should generate avatars for non-users,
        # but this test just validates the current code's behavior.
        self.login("hamlet")

        response = self.client_get("/avatar/nonexistent_user@zulip.com", {"foo": "bar"})
        redirect_url = response["Location"]
        actual_url = "https://secure.gravatar.com/avatar/444258b521f152129eb0c162996e572d?d=identicon&version=1&foo=bar"
        self.assertEqual(redirect_url, actual_url)

    def test_valid_avatars(self) -> None:
        """
        A PUT request to /json/users/me/avatar with a valid file should return a URL and actually create an avatar.
        """
        version = 2
        for fname, rfname in self.correct_files:
            with self.subTest(fname=fname):
                self.login("hamlet")
                with get_test_image_file(fname) as fp:
                    result = self.client_post("/json/users/me/avatar", {"file": fp})

                response_dict = self.assert_json_success(result)
                self.assertIn("avatar_url", response_dict)
                base = "/user_avatars/"
                url = self.assert_json_success(result)["avatar_url"]
                self.assertEqual(base, url[: len(base)])

                if rfname is not None:
                    response = self.client_get(url)
                    data = response.getvalue()
                    avatar_image = pyvips.Image.new_from_buffer(data, "")
                    self.assertEqual(avatar_image.height, 100)
                    self.assertEqual(avatar_image.width, 100)

                # Verify that the medium-size avatar was created
                user_profile = self.example_user("hamlet")
                medium_avatar_disk_path = avatar_disk_path(user_profile, medium=True)
                self.assertTrue(os.path.exists(medium_avatar_disk_path))

                # Verify that ensure_medium_avatar_url does not overwrite this file if it exists
                with mock.patch(
                    "zerver.lib.upload.local.write_local_file"
                ) as mock_write_local_file:
                    zerver.lib.upload.ensure_avatar_image(user_profile, medium=True)
                    self.assertFalse(mock_write_local_file.called)

                # Confirm that ensure_medium_avatar_url works to recreate
                # medium size avatars from the original if needed
                os.remove(medium_avatar_disk_path)
                self.assertFalse(os.path.exists(medium_avatar_disk_path))
                zerver.lib.upload.ensure_avatar_image(user_profile, medium=True)
                self.assertTrue(os.path.exists(medium_avatar_disk_path))

                # Verify whether the avatar_version gets incremented with every new upload
                self.assertEqual(user_profile.avatar_version, version)
                version += 1

    def test_copy_avatar_image(self) -> None:
        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            self.client_post("/json/users/me/avatar", {"file": image_file})

        source_user_profile = self.example_user("hamlet")
        target_user_profile = do_create_user(
            "user@zulip.com", "password", get_realm("zulip"), "user", acting_user=None
        )

        # 'visibility_policy_banner' is already marked as read for new users.
        # Delete that row to avoid integrity error in copy_default_settings.
        OnboardingStep.objects.filter(
            user=target_user_profile, onboarding_step="visibility_policy_banner"
        ).delete()

        copy_default_settings(source_user_profile, target_user_profile)

        source_path_id = avatar_disk_path(source_user_profile)
        target_path_id = avatar_disk_path(target_user_profile)
        self.assertNotEqual(source_path_id, target_path_id)
        with open(source_path_id, "rb") as source, open(target_path_id, "rb") as target:
            self.assertEqual(source.read(), target.read())

        source_original_path_id = avatar_disk_path(source_user_profile, original=True)
        target_original_path_id = avatar_disk_path(target_user_profile, original=True)
        with (
            open(source_original_path_id, "rb") as source,
            open(target_original_path_id, "rb") as target,
        ):
            self.assertEqual(source.read(), target.read())

        source_medium_path_id = avatar_disk_path(source_user_profile, medium=True)
        target_medium_path_id = avatar_disk_path(target_user_profile, medium=True)
        with (
            open(source_medium_path_id, "rb") as source,
            open(target_medium_path_id, "rb") as target,
        ):
            self.assertEqual(source.read(), target.read())

    def test_delete_avatar_image(self) -> None:
        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            self.client_post("/json/users/me/avatar", {"file": image_file})

        user = self.example_user("hamlet")

        avatar_path_id = avatar_disk_path(user)
        avatar_original_path_id = avatar_disk_path(user, original=True)
        avatar_medium_path_id = avatar_disk_path(user, medium=True)

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.isfile(avatar_path_id))
        self.assertTrue(os.path.isfile(avatar_original_path_id))
        self.assertTrue(os.path.isfile(avatar_medium_path_id))

        do_delete_avatar_image(user, acting_user=user)

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)
        self.assertFalse(os.path.isfile(avatar_path_id))
        self.assertFalse(os.path.isfile(avatar_original_path_id))
        self.assertFalse(os.path.isfile(avatar_medium_path_id))

    def test_invalid_avatars(self) -> None:
        """
        A PUT request to /json/users/me/avatar with an invalid file should fail.
        """
        corrupt_files = [
            ("text.txt", False),
            ("unsupported.bmp", False),
            ("actually-a-bmp.png", True),
            ("corrupt.png", True),
            ("corrupt.gif", True),
        ]
        for fname, is_valid_image_format in corrupt_files:
            with self.subTest(fname=fname):
                if not at_least_libvips(8, 13) and "actually-a-" in fname:  # nocoverage
                    self.skipTest(
                        f"libvips is only version {libvips_version(0)}.{libvips_version(1)}"
                    )
                self.login("hamlet")
                with get_test_image_file(fname) as fp:
                    result = self.client_post("/json/users/me/avatar", {"file": fp})

                if is_valid_image_format:
                    self.assert_json_error(
                        result, "Could not decode image; did you upload an image file?"
                    )
                else:
                    self.assert_json_error(result, "Invalid image format")
                user_profile = self.example_user("hamlet")
                self.assertEqual(user_profile.avatar_version, 1)

    def test_delete_avatar(self) -> None:
        """
        A DELETE request to /json/users/me/avatar should delete the profile picture and return gravatar URL
        """
        self.login("cordelia")
        cordelia = self.example_user("cordelia")
        cordelia.avatar_source = UserProfile.AVATAR_FROM_USER
        cordelia.save()

        do_set_realm_property(cordelia.realm, "avatar_changes_disabled", True, acting_user=None)
        result = self.client_delete("/json/users/me/avatar")
        self.assert_json_error(result, "Avatar changes are disabled in this organization.", 400)

        do_set_realm_property(cordelia.realm, "avatar_changes_disabled", False, acting_user=None)
        result = self.client_delete("/json/users/me/avatar")
        user_profile = self.example_user("cordelia")

        response_dict = self.assert_json_success(result)
        self.assertIn("avatar_url", response_dict)
        self.assertEqual(response_dict["avatar_url"], avatar_url(user_profile))

        self.assertEqual(user_profile.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)
        self.assertEqual(user_profile.avatar_version, 2)

    def test_avatar_upload_file_size_error(self) -> None:
        self.login("hamlet")
        with (
            get_test_image_file(self.correct_files[0][0]) as fp,
            self.settings(MAX_AVATAR_FILE_SIZE_MIB=0),
        ):
            result = self.client_post("/json/users/me/avatar", {"file": fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MiB")

    def test_system_bot_avatars_url(self) -> None:
        self.login("hamlet")
        system_bot_emails = [
            settings.NOTIFICATION_BOT,
            settings.WELCOME_BOT,
            settings.EMAIL_GATEWAY_BOT,
        ]
        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        default_avatar = DEFAULT_AVATAR_FILE

        for email in system_bot_emails:
            system_bot = get_system_bot(email, internal_realm.id)
            response = self.client_get(f"/avatar/{email}")
            redirect_url = response["Location"]
            self.assertEqual(redirect_url, str(avatar_url(system_bot)))

            response = self.client_get(f"/avatar/{email}/medium")
            redirect_url = response["Location"]
            self.assertEqual(redirect_url, str(avatar_url(system_bot, medium=True)))

        with (
            self.settings(STATIC_ROOT="static/"),
            patch("zerver.lib.avatar.staticfiles_storage.exists") as mock_exists,
        ):
            mock_exists.return_value = False
            static_avatar_url = get_static_avatar_url("false-bot@zulip.com", False)
        self.assertIn(default_avatar, static_avatar_url)

        with self.settings(DEBUG=True), self.assertRaises(AssertionError) as e:
            get_static_avatar_url("false-bot@zulip.com", False)
        expected_error_message = "Unknown avatar file for: false-bot@zulip.com"
        self.assertEqual(str(e.exception), expected_error_message)


class RealmIconTest(UploadSerializeMixin, ZulipTestCase):
    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        # Log in as admin
        self.login("iago")
        with get_test_image_file("img.png") as fp1, get_test_image_file("img.png") as fp2:
            result = self.client_post("/json/realm/icon", {"f1": fp1, "f2": fp2})
        self.assert_json_error(result, "You must upload exactly one icon.")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login("iago")

        result = self.client_post("/json/realm/icon")
        self.assert_json_error(result, "You must upload exactly one icon.")

    correct_files = [
        ("img.png", "png_resized.png"),
        ("img.jpg", None),  # jpeg resizing is platform-dependent
        ("img.gif", "gif_resized.png"),
        ("img.tif", "tif_resized.png"),
        ("cmyk.jpg", None),
    ]

    def test_no_admin_user_upload(self) -> None:
        self.login("hamlet")
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_post("/json/realm/icon", {"file": fp})
        self.assert_json_error(result, "Must be an organization administrator")

    def test_get_gravatar_icon(self) -> None:
        self.login("hamlet")
        realm = get_realm("zulip")
        do_change_icon_source(realm, Realm.ICON_FROM_GRAVATAR, acting_user=None)
        with self.settings(ENABLE_GRAVATAR=True):
            response = self.client_get("/json/realm/icon", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertEqual(redirect_url, realm_icon_url(realm) + "&foo=bar")

        with self.settings(ENABLE_GRAVATAR=False):
            response = self.client_get("/json/realm/icon", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertTrue(redirect_url.endswith(realm_icon_url(realm) + "&foo=bar"))

    def test_get_settings_realm_icon(self) -> None:
        self.login("hamlet")
        with self.settings(
            ENABLE_GRAVATAR=False, DEFAULT_AVATAR_URI="http://other.server/icon.svg"
        ):
            response = self.client_get("/json/realm/icon", {"foo": "bar"})
            redirect_url = response["Location"]
            self.assertEqual(redirect_url, "http://other.server/icon.svg?foo=bar")

    def test_get_uploaded_realm_icon(self) -> None:
        self.login("hamlet")

        realm = get_realm("zulip")
        do_change_icon_source(realm, Realm.ICON_UPLOADED, acting_user=None)
        response = self.client_get("/json/realm/icon", {"foo": "bar"})
        redirect_url = response["Location"]
        self.assertTrue(redirect_url.endswith(realm_icon_url(realm) + "&foo=bar"))

    def test_valid_icons(self) -> None:
        """
        A PUT request to /json/realm/icon with a valid file should return a URL
        and actually create an realm icon.
        """
        for fname, rfname in self.correct_files:
            with self.subTest(fname=fname):
                self.login("iago")
                with get_test_image_file(fname) as fp:
                    result = self.client_post("/json/realm/icon", {"file": fp})
                realm = get_realm("zulip")
                response_dict = self.assert_json_success(result)
                self.assertIn("icon_url", response_dict)
                base = f"/user_avatars/{realm.id}/realm/icon.png"
                url = response_dict["icon_url"]
                self.assertEqual(base, url[: len(base)])

                if rfname is not None:
                    response = self.client_get(url)
                    data = response.getvalue()
                    response_image = pyvips.Image.new_from_buffer(data, "")
                    self.assertEqual(response_image.height, 100)
                    self.assertEqual(response_image.width, 100)

    def test_invalid_icons(self) -> None:
        """
        A PUT request to /json/realm/icon with an invalid file should fail.
        """
        corrupt_files = [
            ("text.txt", False),
            ("unsupported.bmp", False),
            ("corrupt.png", True),
            ("corrupt.gif", True),
        ]
        for fname, is_valid_image_format in corrupt_files:
            with self.subTest(fname=fname):
                self.login("iago")
                with get_test_image_file(fname) as fp:
                    result = self.client_post("/json/realm/icon", {"file": fp})

                if is_valid_image_format:
                    self.assert_json_error(
                        result, "Could not decode image; did you upload an image file?"
                    )
                else:
                    self.assert_json_error(result, "Invalid image format")

    def test_delete_icon(self) -> None:
        """
        A DELETE request to /json/realm/icon should delete the realm icon and return gravatar URL
        """
        self.login("iago")
        realm = get_realm("zulip")
        do_change_icon_source(realm, Realm.ICON_UPLOADED, acting_user=None)

        result = self.client_delete("/json/realm/icon")

        response_dict = self.assert_json_success(result)
        self.assertIn("icon_url", response_dict)
        realm = get_realm("zulip")
        self.assertEqual(response_dict["icon_url"], realm_icon_url(realm))
        self.assertEqual(realm.icon_source, Realm.ICON_FROM_GRAVATAR)

    def test_realm_icon_version(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        icon_version = realm.icon_version
        self.assertEqual(icon_version, 1)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            self.client_post("/json/realm/icon", {"file": fp})
        realm = get_realm("zulip")
        self.assertEqual(realm.icon_version, icon_version + 1)

    def test_realm_icon_upload_file_size_error(self) -> None:
        self.login("iago")
        with (
            get_test_image_file(self.correct_files[0][0]) as fp,
            self.settings(MAX_ICON_FILE_SIZE_MIB=0),
        ):
            result = self.client_post("/json/realm/icon", {"file": fp})
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MiB")


class RealmLogoTest(UploadSerializeMixin, ZulipTestCase):
    night = False

    def test_multiple_upload_failure(self) -> None:
        """
        Attempting to upload two files should fail.
        """
        # Log in as admin
        self.login("iago")
        with get_test_image_file("img.png") as fp1, get_test_image_file("img.png") as fp2:
            result = self.client_post(
                "/json/realm/logo",
                {"f1": fp1, "f2": fp2, "night": orjson.dumps(self.night).decode()},
            )
        self.assert_json_error(result, "You must upload exactly one logo.")

    def test_no_file_upload_failure(self) -> None:
        """
        Calling this endpoint with no files should fail.
        """
        self.login("iago")

        result = self.client_post("/json/realm/logo", {"night": orjson.dumps(self.night).decode()})
        self.assert_json_error(result, "You must upload exactly one logo.")

    correct_files = [
        ("img.png", "png_resized.png"),
        ("img.jpg", None),  # jpeg resizing is platform-dependent
        ("img.gif", "gif_resized.png"),
        ("img.tif", "tif_resized.png"),
        ("cmyk.jpg", None),
    ]

    def test_no_admin_user_upload(self) -> None:
        self.login("hamlet")
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_post(
                "/json/realm/logo", {"file": fp, "night": orjson.dumps(self.night).decode()}
            )
        self.assert_json_error(result, "Must be an organization administrator")

    def test_upload_limited_plan_type(self) -> None:
        user_profile = self.example_user("iago")
        do_change_realm_plan_type(user_profile.realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
        self.login_user(user_profile)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            result = self.client_post(
                "/json/realm/logo", {"file": fp, "night": orjson.dumps(self.night).decode()}
            )
        self.assert_json_error(result, "Available on Zulip Cloud Standard. Upgrade to access.")

    def test_get_default_logo(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        do_change_logo_source(realm, Realm.LOGO_DEFAULT, self.night, acting_user=user_profile)
        response = self.client_get("/json/realm/logo", {"night": orjson.dumps(self.night).decode()})
        redirect_url = response["Location"]
        is_night_str = str(self.night).lower()
        self.assertEqual(
            redirect_url,
            f"http://testserver/static/images/logo/zulip-org-logo.svg?version=0&night={is_night_str}",
        )

    def test_get_settings_logo(self) -> None:
        self.login("hamlet")
        with self.settings(DEFAULT_LOGO_URI="http://other.server/logo.svg"):
            response = self.client_get(
                "/json/realm/logo", {"night": orjson.dumps(self.night).decode()}
            )
            redirect_url = response["Location"]
            self.assertEqual(
                redirect_url,
                f"http://other.server/logo.svg?night={str(self.night).lower()}",
            )

    def test_get_realm_logo(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        do_change_logo_source(realm, Realm.LOGO_UPLOADED, self.night, acting_user=user_profile)
        response = self.client_get("/json/realm/logo", {"night": orjson.dumps(self.night).decode()})
        redirect_url = response["Location"]
        self.assertTrue(
            redirect_url.endswith(
                get_realm_logo_url(realm, self.night) + f"&night={str(self.night).lower()}"
            )
        )

        is_night_str = str(self.night).lower()

        if self.night:
            file_name = "night_logo.png"
        else:
            file_name = "logo.png"
        self.assertEqual(
            redirect_url,
            f"/user_avatars/{realm.id}/realm/{file_name}?version=2&night={is_night_str}",
        )

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=user_profile)
        if self.night:
            self.assertEqual(realm.night_logo_source, Realm.LOGO_UPLOADED)
        else:
            self.assertEqual(realm.logo_source, Realm.LOGO_UPLOADED)
        response = self.client_get("/json/realm/logo", {"night": orjson.dumps(self.night).decode()})
        redirect_url = response["Location"]
        self.assertEqual(
            redirect_url,
            f"http://testserver/static/images/logo/zulip-org-logo.svg?version=0&night={is_night_str}",
        )

    def test_valid_logos(self) -> None:
        """
        A PUT request to /json/realm/logo with a valid file should return a URL
        and actually create an realm logo.
        """
        for fname, rfname in self.correct_files:
            with self.subTest(fname=fname):
                self.login("iago")
                with get_test_image_file(fname) as fp:
                    result = self.client_post(
                        "/json/realm/logo", {"file": fp, "night": orjson.dumps(self.night).decode()}
                    )
                realm = get_realm("zulip")
                self.assert_json_success(result)
                logo_url = get_realm_logo_url(realm, self.night)

                if rfname is not None:
                    response = self.client_get(logo_url)
                    data = response.getvalue()
                    # size should be 100 x 100 because thumbnail keeps aspect ratio
                    # while trying to fit in a 800 x 100 box without losing part of the image
                    response_image = pyvips.Image.new_from_buffer(data, "")
                    self.assertEqual(response_image.height, 100)
                    self.assertEqual(response_image.width, 100)

    def test_invalid_logo_upload(self) -> None:
        """
        A PUT request to /json/realm/logo with an invalid file should fail.
        """
        corrupt_files = [
            ("text.txt", False),
            ("unsupported.bmp", False),
            ("corrupt.png", True),
            ("corrupt.gif", True),
        ]
        for fname, is_valid_image_format in corrupt_files:
            with self.subTest(fname=fname):
                self.login("iago")
                with get_test_image_file(fname) as fp:
                    result = self.client_post(
                        "/json/realm/logo", {"file": fp, "night": orjson.dumps(self.night).decode()}
                    )

                if is_valid_image_format:
                    self.assert_json_error(
                        result, "Could not decode image; did you upload an image file?"
                    )
                else:
                    self.assert_json_error(result, "Invalid image format")

    def test_delete_logo(self) -> None:
        """
        A DELETE request to /json/realm/logo should delete the realm logo and return gravatar URL
        """
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        realm = user_profile.realm
        do_change_logo_source(realm, Realm.LOGO_UPLOADED, self.night, acting_user=user_profile)
        result = self.client_delete(
            "/json/realm/logo", {"night": orjson.dumps(self.night).decode()}
        )
        self.assert_json_success(result)
        realm = get_realm("zulip")
        if self.night:
            self.assertEqual(realm.night_logo_source, Realm.LOGO_DEFAULT)
        else:
            self.assertEqual(realm.logo_source, Realm.LOGO_DEFAULT)

    def test_logo_version(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        if self.night:
            version = realm.night_logo_version
        else:
            version = realm.logo_version
        self.assertEqual(version, 1)
        with get_test_image_file(self.correct_files[0][0]) as fp:
            self.client_post(
                "/json/realm/logo", {"file": fp, "night": orjson.dumps(self.night).decode()}
            )
        realm = get_realm("zulip")
        if self.night:
            self.assertEqual(realm.night_logo_version, version + 1)
        else:
            self.assertEqual(realm.logo_version, version + 1)

    def test_logo_upload_file_size_error(self) -> None:
        self.login("iago")
        with (
            get_test_image_file(self.correct_files[0][0]) as fp,
            self.settings(MAX_LOGO_FILE_SIZE_MIB=0),
        ):
            result = self.client_post(
                "/json/realm/logo", {"file": fp, "night": orjson.dumps(self.night).decode()}
            )
        self.assert_json_error(result, "Uploaded file is larger than the allowed limit of 0 MiB")


class RealmNightLogoTest(RealmLogoTest):
    # Run the same tests as for RealmLogoTest, just with dark theme enabled
    night = True


class EmojiTest(UploadSerializeMixin, ZulipTestCase):
    def test_upload_emoji(self) -> None:
        self.login("iago")
        with get_test_image_file("img.png") as f:
            result = self.client_post("/json/realm/emoji/new", {"f1": f})
            self.assert_json_success(result)

    def test_non_image(self) -> None:
        """Non-image is not resized"""
        self.login("iago")
        with (
            get_test_image_file("text.txt") as f,
            patch("zerver.lib.upload.resize_emoji", return_value=(b"a", None)) as resize_mock,
        ):
            result = self.client_post("/json/realm/emoji/new", {"f1": f})
            self.assert_json_error(result, "Invalid image format")
            resize_mock.assert_not_called()

    def test_unsupported_format(self) -> None:
        """Invalid format is not resized"""
        self.login("iago")
        with (
            get_test_image_file("img.bmp") as f,
            patch("zerver.lib.upload.resize_emoji", return_value=(b"a", None)) as resize_mock,
        ):
            result = self.client_post("/json/realm/emoji/new", {"f1": f})
            self.assert_json_error(result, "Invalid image format")
            resize_mock.assert_not_called()

    def test_upload_too_big_after_resize(self) -> None:
        """Non-animated image is too big after resizing"""
        self.login("iago")
        with (
            get_test_image_file("img.png") as f,
            patch(
                "zerver.lib.upload.resize_emoji", return_value=(b"a" * (200 * 1024), None)
            ) as resize_mock,
        ):
            result = self.client_post("/json/realm/emoji/new", {"f1": f})
            self.assert_json_error(result, "Image size exceeds limit")
            resize_mock.assert_called_once()

    def test_upload_big_after_animated_resize(self) -> None:
        """A big animated image is fine as long as the still is small"""
        self.login("iago")
        with (
            get_test_image_file("animated_img.gif") as f,
            patch(
                "zerver.lib.upload.resize_emoji", return_value=(b"a" * (200 * 1024), b"aaa")
            ) as resize_mock,
        ):
            result = self.client_post("/json/realm/emoji/new", {"f1": f})
            self.assert_json_success(result)
            resize_mock.assert_called_once()

    def test_upload_too_big_after_animated_resize_still(self) -> None:
        """Still of animated image is too big after resizing"""
        self.login("iago")
        with (
            get_test_image_file("animated_img.gif") as f,
            patch(
                "zerver.lib.upload.resize_emoji", return_value=(b"aaa", b"a" * (200 * 1024))
            ) as resize_mock,
        ):
            result = self.client_post("/json/realm/emoji/new", {"f1": f})
            self.assert_json_error(result, "Image size exceeds limit")
            resize_mock.assert_called_once()


class SanitizeNameTests(ZulipTestCase):
    def test_file_name(self) -> None:
        self.assertEqual(sanitize_name("test.txt"), "test.txt")
        self.assertEqual(sanitize_name(".hidden"), ".hidden")
        self.assertEqual(sanitize_name(".hidden.txt"), ".hidden.txt")
        self.assertEqual(sanitize_name("tarball.tar.gz"), "tarball.tar.gz")
        self.assertEqual(sanitize_name(".hidden_tarball.tar.gz"), ".hidden_tarball.tar.gz")
        self.assertEqual(sanitize_name("Testing{}*&*#().ta&&%$##&&r.gz"), "Testing.tar.gz")
        self.assertEqual(sanitize_name("*testingfile?*.txt"), "testingfile.txt")
        self.assertEqual(sanitize_name("snowman☃.txt"), "snowman.txt")
        self.assertEqual(sanitize_name("테스트.txt"), "테스트.txt")
        self.assertEqual(
            sanitize_name('~/."\\`\\?*"u0`000ssh/test.t**{}ar.gz'), ".u0000sshtest.tar.gz"
        )


class UploadSpaceTests(UploadSerializeMixin, ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.user_profile = self.example_user("hamlet")

    def test_currently_used_upload_space(self) -> None:
        self.assertEqual(None, cache_get(get_realm_used_upload_space_cache_key(self.realm.id)))
        self.assertEqual(0, self.realm.currently_used_upload_space_bytes())
        self.assertEqual(0, cache_get(get_realm_used_upload_space_cache_key(self.realm.id))[0])

        data = b"zulip!"
        upload_message_attachment("dummy.txt", "text/plain", data, self.user_profile)
        # notify_attachment_update function calls currently_used_upload_space_bytes which
        # updates the cache.
        self.assert_length(data, cache_get(get_realm_used_upload_space_cache_key(self.realm.id))[0])
        self.assert_length(data, self.realm.currently_used_upload_space_bytes())

        data2 = b"more-data!"
        upload_message_attachment("dummy2.txt", "text/plain", data2, self.user_profile)
        self.assertEqual(
            len(data) + len(data2),
            cache_get(get_realm_used_upload_space_cache_key(self.realm.id))[0],
        )
        self.assertEqual(len(data) + len(data2), self.realm.currently_used_upload_space_bytes())

        attachment = Attachment.objects.get(file_name="dummy.txt")
        attachment.file_name = "dummy1.txt"
        attachment.save(update_fields=["file_name"])
        self.assertEqual(
            len(data) + len(data2),
            cache_get(get_realm_used_upload_space_cache_key(self.realm.id))[0],
        )
        self.assertEqual(len(data) + len(data2), self.realm.currently_used_upload_space_bytes())

        attachment.delete()
        self.assertEqual(None, cache_get(get_realm_used_upload_space_cache_key(self.realm.id)))
        self.assert_length(data2, self.realm.currently_used_upload_space_bytes())

        now = timezone_now()
        RealmCount.objects.create(
            realm=self.realm,
            property="upload_quota_used_bytes::day",
            end_time=now,
            value=len(data2),
        )
        # Purge the cache since we want to actually execute the function.
        cache_delete(get_realm_used_upload_space_cache_key(self.realm.id))

        self.assert_length(data2, self.realm.currently_used_upload_space_bytes())

        data3 = b"even-more-data!"
        upload_message_attachment("dummy3.txt", "text/plain", data3, self.user_profile)
        self.assertEqual(len(data2) + len(data3), self.realm.currently_used_upload_space_bytes())


class DecompressionBombTests(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.test_urls = [
            "/json/users/me/avatar",
            "/json/realm/logo",
            "/json/realm/icon",
            "/json/realm/emoji/bomb_emoji",
        ]

    def test_decompression_bomb(self) -> None:
        self.login("iago")
        with get_test_image_file("bomb.png") as fp:
            for url in self.test_urls:
                fp.seek(0, 0)
                if url == "/json/realm/logo":
                    result = self.client_post(
                        url, {"f1": fp, "night": orjson.dumps(False).decode()}
                    )
                else:
                    result = self.client_post(url, {"f1": fp})
                self.assert_json_error(result, "Image size exceeds limit.")
