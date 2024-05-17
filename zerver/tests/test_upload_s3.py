import io
import os
import re
from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.parse import urlsplit

import botocore.exceptions
from django.conf import settings
from PIL import Image

import zerver.lib.upload
from zerver.actions.user_settings import do_delete_avatar_image
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.create_user import copy_default_settings
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    create_s3_buckets,
    get_test_image_file,
    read_test_image_file,
    use_s3_backend,
)
from zerver.lib.upload import (
    all_message_attachments,
    delete_export_tarball,
    delete_message_attachment,
    delete_message_attachments,
    save_attachment_contents,
    upload_export_tarball,
    upload_message_attachment,
)
from zerver.lib.upload.base import (
    DEFAULT_AVATAR_SIZE,
    DEFAULT_EMOJI_SIZE,
    MEDIUM_AVATAR_SIZE,
    resize_avatar,
)
from zerver.lib.upload.s3 import S3UploadBackend
from zerver.models import Attachment, RealmEmoji, UserProfile
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot


class S3Test(ZulipTestCase):
    @use_s3_backend
    def test_upload_message_attachment(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        url = upload_message_attachment(
            "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
        )

        base = "/user_uploads/"
        self.assertEqual(base, url[: len(base)])
        path_id = re.sub(r"/user_uploads/", "", url)
        content = bucket.Object(path_id).get()["Body"].read()
        self.assertEqual(b"zulip!", content)

        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assert_length(b"zulip!", uploaded_file.size)

        self.subscribe(self.example_user("hamlet"), "Denmark")
        body = f"First message ...[zulip.txt](http://{user_profile.realm.host}{url})"
        self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test")

    @use_s3_backend
    def test_save_attachment_contents(self) -> None:
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)
        user_profile = self.example_user("hamlet")
        url = upload_message_attachment(
            "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
        )

        path_id = re.sub(r"/user_uploads/", "", url)
        output = BytesIO()
        save_attachment_contents(path_id, output)
        self.assertEqual(output.getvalue(), b"zulip!")

    @use_s3_backend
    def test_upload_message_attachment_s3_cross_realm_path(self) -> None:
        """
        Verifies that the path of a file uploaded by a cross-realm bot to another
        realm is correct.
        """
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)

        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        zulip_realm = get_realm("zulip")
        user_profile = get_system_bot(settings.EMAIL_GATEWAY_BOT, internal_realm.id)
        self.assertEqual(user_profile.realm, internal_realm)

        url = upload_message_attachment(
            "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile, zulip_realm
        )
        # Ensure the correct realm id of the target realm is used instead of the bot's realm.
        self.assertTrue(url.startswith(f"/user_uploads/{zulip_realm.id}/"))

    @use_s3_backend
    def test_upload_message_attachment_s3_with_undefined_content_type(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        url = upload_message_attachment("dummy.txt", len(b"zulip!"), None, b"zulip!", user_profile)

        path_id = re.sub(r"/user_uploads/", "", url)
        self.assertEqual(b"zulip!", bucket.Object(path_id).get()["Body"].read())
        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assert_length(b"zulip!", uploaded_file.size)

    @use_s3_backend
    def test_delete_message_attachment(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        url = upload_message_attachment(
            "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
        )

        path_id = re.sub(r"/user_uploads/", "", url)
        self.assertIsNotNone(bucket.Object(path_id).get())
        self.assertTrue(delete_message_attachment(path_id))
        with self.assertRaises(botocore.exceptions.ClientError):
            bucket.Object(path_id).load()

    @use_s3_backend
    def test_delete_message_attachments(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        path_ids = []
        for n in range(1, 5):
            url = upload_message_attachment(
                "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
            )
            path_id = re.sub(r"/user_uploads/", "", url)
            self.assertIsNotNone(bucket.Object(path_id).get())
            path_ids.append(path_id)

        with patch.object(S3UploadBackend, "delete_message_attachment") as single_delete:
            delete_message_attachments(path_ids)
            single_delete.assert_not_called()
        for path_id in path_ids:
            with self.assertRaises(botocore.exceptions.ClientError):
                bucket.Object(path_id).load()

    @use_s3_backend
    def test_delete_message_attachment_when_file_doesnt_exist(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]
        with self.assertRaises(botocore.exceptions.ClientError):
            bucket.Object("non-existent-file").load()
        with self.assertLogs(level="WARNING") as warn_log:
            self.assertEqual(False, delete_message_attachment("non-existent-file"))
        self.assertEqual(
            warn_log.output,
            [
                "WARNING:root:non-existent-file does not exist. Its entry in the database will be removed."
            ],
        )

    @use_s3_backend
    def test_all_message_attachments(self) -> None:
        create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)

        user_profile = self.example_user("hamlet")
        path_ids = []
        for n in range(1, 5):
            url = upload_message_attachment(
                "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
            )
            path_ids.append(re.sub(r"/user_uploads/", "", url))
        found_paths = [r[0] for r in all_message_attachments()]
        self.assertEqual(sorted(found_paths), sorted(path_ids))

    @use_s3_backend
    def test_user_uploads_authed(self) -> None:
        """
        A call to /json/user_uploads should return a url and actually create an object.
        """
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]

        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/user_uploads", {"file": fp})
        response_dict = self.assert_json_success(result)
        self.assertIn("uri", response_dict)
        base = "/user_uploads/"
        url = response_dict["uri"]
        self.assertEqual(base, url[: len(base)])

        # In development, this is just a redirect
        response = self.client_get(url)
        redirect_url = response["Location"]
        path = urlsplit(redirect_url).path
        assert path.startswith("/")
        key = path[len("/") :]
        self.assertEqual(b"zulip!", bucket.Object(key).get()["Body"].read())

        prefix = f"/internal/s3/{settings.S3_AUTH_UPLOADS_BUCKET}.s3.amazonaws.com/"
        with self.settings(DEVELOPMENT=False):
            response = self.client_get(url)
        redirect_url = response["X-Accel-Redirect"]
        path = urlsplit(redirect_url).path
        assert path.startswith(prefix)
        key = path[len(prefix) :]
        self.assertEqual(b"zulip!", bucket.Object(key).get()["Body"].read())

        # Check the download endpoint
        download_url = url.replace("/user_uploads/", "/user_uploads/download/")
        with self.settings(DEVELOPMENT=False):
            response = self.client_get(download_url)
        redirect_url = response["X-Accel-Redirect"]
        path = urlsplit(redirect_url).path
        assert path.startswith(prefix)
        key = path[len(prefix) :]
        self.assertEqual(b"zulip!", bucket.Object(key).get()["Body"].read())

        # Now try the endpoint that's supposed to return a temporary URL for access
        # to the file.
        result = self.client_get("/json" + url)
        data = self.assert_json_success(result)
        url_only_url = data["url"]

        self.assertNotEqual(url_only_url, url)
        self.assertIn("user_uploads/temporary/", url_only_url)
        self.assertTrue(url_only_url.endswith("zulip.txt"))
        # The generated URL has a token authorizing the requester to access the file
        # without being logged in.
        self.logout()
        with self.settings(DEVELOPMENT=False):
            self.client_get(url_only_url)
        redirect_url = response["X-Accel-Redirect"]
        path = urlsplit(redirect_url).path
        assert path.startswith(prefix)
        key = path[len(prefix) :]
        self.assertEqual(b"zulip!", bucket.Object(key).get()["Body"].read())

        # The original url shouldn't work when logged out:
        with self.settings(DEVELOPMENT=False):
            result = self.client_get(url)
        self.assertEqual(result.status_code, 302)
        self.assertTrue(result.headers["Location"].endswith(f"/login/?next={url}"))

        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        body = f"First message ...[zulip.txt](http://{hamlet.realm.host}" + url + ")"
        self.send_stream_message(hamlet, "Denmark", body, "test")

    @use_s3_backend
    def test_user_avatars_redirect(self) -> None:
        create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]
        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            result = self.client_post("/json/users/me/avatar", {"file": image_file})

        response_dict = self.assert_json_success(result)
        self.assertIn("avatar_url", response_dict)
        base = f"https://{settings.S3_AVATAR_BUCKET}.s3.amazonaws.com/"
        url = self.assert_json_success(result)["avatar_url"]
        self.assertEqual(base, url[: len(base)])

        # Try hitting the equivalent `/user_avatars` endpoint
        wrong_url = "/user_avatars/" + url[len(base) :]
        result = self.client_get(wrong_url)
        self.assertEqual(result.status_code, 301)
        self.assertEqual(result["Location"], url)

    @use_s3_backend
    def test_upload_avatar_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        path_id = user_avatar_path(user_profile)
        original_image_path_id = path_id + ".original"
        medium_path_id = path_id + "-medium.png"

        with get_test_image_file("img.png") as image_file:
            zerver.lib.upload.upload_backend.upload_avatar_image(
                image_file, user_profile, user_profile
            )
        test_image_data = read_test_image_file("img.png")
        test_medium_image_data = resize_avatar(test_image_data, MEDIUM_AVATAR_SIZE)

        original_image_key = bucket.Object(original_image_path_id)
        self.assertEqual(original_image_key.key, original_image_path_id)
        image_data = original_image_key.get()["Body"].read()
        self.assertEqual(image_data, test_image_data)

        medium_image_key = bucket.Object(medium_path_id)
        self.assertEqual(medium_image_key.key, medium_path_id)
        medium_image_data = medium_image_key.get()["Body"].read()
        self.assertEqual(medium_image_data, test_medium_image_data)

        bucket.Object(medium_image_key.key).delete()
        zerver.lib.upload.upload_backend.ensure_avatar_image(user_profile, is_medium=True)
        medium_image_key = bucket.Object(medium_path_id)
        self.assertEqual(medium_image_key.key, medium_path_id)

    @use_s3_backend
    def test_copy_avatar_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            self.client_post("/json/users/me/avatar", {"file": image_file})

        source_user_profile = self.example_user("hamlet")
        target_user_profile = self.example_user("othello")

        copy_default_settings(source_user_profile, target_user_profile)

        source_path_id = user_avatar_path(source_user_profile)
        target_path_id = user_avatar_path(target_user_profile)
        self.assertNotEqual(source_path_id, target_path_id)

        source_image_key = bucket.Object(source_path_id)
        target_image_key = bucket.Object(target_path_id)
        self.assertEqual(target_image_key.key, target_path_id)
        self.assertEqual(source_image_key.content_type, target_image_key.content_type)
        source_image_data = source_image_key.get()["Body"].read()
        target_image_data = target_image_key.get()["Body"].read()

        source_original_image_path_id = source_path_id + ".original"
        target_original_image_path_id = target_path_id + ".original"
        target_original_image_key = bucket.Object(target_original_image_path_id)
        self.assertEqual(target_original_image_key.key, target_original_image_path_id)
        source_original_image_key = bucket.Object(source_original_image_path_id)
        self.assertEqual(
            source_original_image_key.content_type, target_original_image_key.content_type
        )
        source_image_data = source_original_image_key.get()["Body"].read()
        target_image_data = target_original_image_key.get()["Body"].read()
        self.assertEqual(source_image_data, target_image_data)

        target_medium_path_id = target_path_id + "-medium.png"
        source_medium_path_id = source_path_id + "-medium.png"
        source_medium_image_key = bucket.Object(source_medium_path_id)
        target_medium_image_key = bucket.Object(target_medium_path_id)
        self.assertEqual(target_medium_image_key.key, target_medium_path_id)
        self.assertEqual(source_medium_image_key.content_type, target_medium_image_key.content_type)
        source_medium_image_data = source_medium_image_key.get()["Body"].read()
        target_medium_image_data = target_medium_image_key.get()["Body"].read()
        self.assertEqual(source_medium_image_data, target_medium_image_data)

    @use_s3_backend
    def test_ensure_avatar_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        base_file_path = user_avatar_path(user_profile)
        # Bug: This should have + ".png", but the implementation is wrong.
        file_path = base_file_path
        original_file_path = base_file_path + ".original"
        medium_file_path = base_file_path + "-medium.png"

        with get_test_image_file("img.png") as image_file:
            zerver.lib.upload.upload_backend.upload_avatar_image(
                image_file, user_profile, user_profile
            )

        key = bucket.Object(original_file_path)
        image_data = key.get()["Body"].read()

        zerver.lib.upload.upload_backend.ensure_avatar_image(user_profile)
        resized_avatar = resize_avatar(image_data)
        key = bucket.Object(file_path)
        self.assertEqual(resized_avatar, key.get()["Body"].read())

        zerver.lib.upload.upload_backend.ensure_avatar_image(user_profile, is_medium=True)
        resized_avatar = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        key = bucket.Object(medium_file_path)
        self.assertEqual(resized_avatar, key.get()["Body"].read())

    @use_s3_backend
    def test_delete_avatar_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            self.client_post("/json/users/me/avatar", {"file": image_file})

        user = self.example_user("hamlet")

        avatar_path_id = user_avatar_path(user)
        avatar_original_image_path_id = avatar_path_id + ".original"
        avatar_medium_path_id = avatar_path_id + "-medium.png"

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertIsNotNone(bucket.Object(avatar_path_id))
        self.assertIsNotNone(bucket.Object(avatar_original_image_path_id))
        self.assertIsNotNone(bucket.Object(avatar_medium_path_id))

        do_delete_avatar_image(user, acting_user=user)

        self.assertEqual(user.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)

        # Confirm that the avatar files no longer exist in S3.
        with self.assertRaises(botocore.exceptions.ClientError):
            bucket.Object(avatar_path_id).load()
        with self.assertRaises(botocore.exceptions.ClientError):
            bucket.Object(avatar_original_image_path_id).load()
        with self.assertRaises(botocore.exceptions.ClientError):
            bucket.Object(avatar_medium_path_id).load()

    @use_s3_backend
    def test_upload_realm_icon_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        with get_test_image_file("img.png") as image_file:
            zerver.lib.upload.upload_backend.upload_realm_icon_image(image_file, user_profile)

        original_path_id = os.path.join(str(user_profile.realm.id), "realm", "icon.original")
        original_key = bucket.Object(original_path_id)
        self.assertEqual(read_test_image_file("img.png"), original_key.get()["Body"].read())

        resized_path_id = os.path.join(str(user_profile.realm.id), "realm", "icon.png")
        resized_data = bucket.Object(resized_path_id).get()["Body"].read()
        # while trying to fit in a 800 x 100 box without losing part of the image
        resized_image = Image.open(io.BytesIO(resized_data)).size
        self.assertEqual(resized_image, (DEFAULT_AVATAR_SIZE, DEFAULT_AVATAR_SIZE))

    @use_s3_backend
    def _test_upload_logo_image(self, night: bool, file_name: str) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        with get_test_image_file("img.png") as image_file:
            zerver.lib.upload.upload_backend.upload_realm_logo_image(
                image_file, user_profile, night
            )

        original_path_id = os.path.join(
            str(user_profile.realm.id), "realm", f"{file_name}.original"
        )
        original_key = bucket.Object(original_path_id)
        self.assertEqual(read_test_image_file("img.png"), original_key.get()["Body"].read())

        resized_path_id = os.path.join(str(user_profile.realm.id), "realm", f"{file_name}.png")
        resized_data = bucket.Object(resized_path_id).get()["Body"].read()
        resized_image = Image.open(io.BytesIO(resized_data)).size
        self.assertEqual(resized_image, (DEFAULT_AVATAR_SIZE, DEFAULT_AVATAR_SIZE))

    def test_upload_realm_logo_image(self) -> None:
        self._test_upload_logo_image(night=False, file_name="logo")
        self._test_upload_logo_image(night=True, file_name="night_logo")

    @use_s3_backend
    def test_get_emoji_url(self) -> None:
        emoji_name = "emoji.png"
        realm_id = 1
        bucket = settings.S3_AVATAR_BUCKET
        path = RealmEmoji.PATH_ID_TEMPLATE.format(realm_id=realm_id, emoji_file_name=emoji_name)

        url = zerver.lib.upload.upload_backend.get_emoji_url("emoji.png", realm_id)

        expected_url = f"https://{bucket}.s3.amazonaws.com/{path}"
        self.assertEqual(expected_url, url)

        emoji_name = "animated_image.gif"

        path = RealmEmoji.PATH_ID_TEMPLATE.format(realm_id=realm_id, emoji_file_name=emoji_name)
        still_path = RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
            realm_id=realm_id, emoji_filename_without_extension=os.path.splitext(emoji_name)[0]
        )

        url = zerver.lib.upload.upload_backend.get_emoji_url("animated_image.gif", realm_id)
        still_url = zerver.lib.upload.upload_backend.get_emoji_url(
            "animated_image.gif", realm_id, still=True
        )

        expected_url = f"https://{bucket}.s3.amazonaws.com/{path}"
        self.assertEqual(expected_url, url)
        expected_still_url = f"https://{bucket}.s3.amazonaws.com/{still_path}"
        self.assertEqual(expected_still_url, still_url)

    @use_s3_backend
    def test_upload_emoji_image(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("hamlet")
        emoji_name = "emoji.png"
        with get_test_image_file("img.png") as image_file:
            zerver.lib.upload.upload_backend.upload_emoji_image(
                image_file, emoji_name, user_profile
            )

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=emoji_name,
        )
        original_key = bucket.Object(emoji_path + ".original")
        self.assertEqual(read_test_image_file("img.png"), original_key.get()["Body"].read())

        resized_data = bucket.Object(emoji_path).get()["Body"].read()
        resized_image = Image.open(io.BytesIO(resized_data))
        self.assertEqual(resized_image.size, (DEFAULT_EMOJI_SIZE, DEFAULT_EMOJI_SIZE))

    @use_s3_backend
    def test_tarball_upload_and_deletion(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        user_profile = self.example_user("iago")
        self.assertTrue(user_profile.is_realm_admin)

        tarball_path = os.path.join(settings.TEST_WORKER_DIR, "tarball.tar.gz")
        with open(tarball_path, "w") as f:
            f.write("dummy")

        total_bytes_transferred = 0

        def percent_callback(bytes_transferred: int) -> None:
            nonlocal total_bytes_transferred
            total_bytes_transferred += bytes_transferred

        url = upload_export_tarball(
            user_profile.realm, tarball_path, percent_callback=percent_callback
        )
        # Verify the percent_callback API works
        self.assertEqual(total_bytes_transferred, 5)

        result = re.search(re.compile(r"([0-9a-fA-F]{32})"), url)
        if result is not None:
            hex_value = result.group(1)
        expected_url = f"https://{bucket.name}.s3.amazonaws.com/exports/{hex_value}/{os.path.basename(tarball_path)}"
        self.assertEqual(url, expected_url)

        # Delete the tarball.
        with self.assertLogs(level="WARNING") as warn_log:
            self.assertIsNone(delete_export_tarball("/not_a_file"))
        self.assertEqual(
            warn_log.output,
            ["WARNING:root:not_a_file does not exist. Its entry in the database will be removed."],
        )
        path_id = urlsplit(url).path
        self.assertEqual(delete_export_tarball(path_id), path_id)
