import os
import re
from io import BytesIO, StringIO
from urllib.parse import urlsplit

from django.conf import settings
from PIL import Image

import zerver.lib.upload
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.test_classes import UploadSerializeMixin, ZulipTestCase
from zerver.lib.test_helpers import get_test_image_file, read_test_image_file
from zerver.lib.upload import (
    all_message_attachments,
    delete_export_tarball,
    delete_message_attachment,
    delete_message_attachments,
    save_attachment_contents,
    upload_emoji_image,
    upload_export_tarball,
    upload_message_attachment,
)
from zerver.lib.upload.base import DEFAULT_EMOJI_SIZE, MEDIUM_AVATAR_SIZE, resize_avatar
from zerver.lib.upload.local import write_local_file
from zerver.models import Attachment, RealmEmoji
from zerver.models.realms import get_realm
from zerver.models.users import get_system_bot


class LocalStorageTest(UploadSerializeMixin, ZulipTestCase):
    def test_upload_message_attachment(self) -> None:
        user_profile = self.example_user("hamlet")
        url = upload_message_attachment(
            "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
        )

        base = "/user_uploads/"
        self.assertEqual(base, url[: len(base)])
        path_id = re.sub(r"/user_uploads/", "", url)
        assert settings.LOCAL_UPLOADS_DIR is not None
        assert settings.LOCAL_FILES_DIR is not None
        file_path = os.path.join(settings.LOCAL_FILES_DIR, path_id)
        self.assertTrue(os.path.isfile(file_path))

        uploaded_file = Attachment.objects.get(owner=user_profile, path_id=path_id)
        self.assert_length(b"zulip!", uploaded_file.size)

    def test_save_attachment_contents(self) -> None:
        user_profile = self.example_user("hamlet")
        url = upload_message_attachment(
            "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
        )

        path_id = re.sub(r"/user_uploads/", "", url)
        output = BytesIO()
        save_attachment_contents(path_id, output)
        self.assertEqual(output.getvalue(), b"zulip!")

    def test_upload_message_attachment_local_cross_realm_path(self) -> None:
        """
        Verifies that the path of a file uploaded by a cross-realm bot to another
        realm is correct.
        """

        internal_realm = get_realm(settings.SYSTEM_BOT_REALM)
        zulip_realm = get_realm("zulip")
        user_profile = get_system_bot(settings.EMAIL_GATEWAY_BOT, internal_realm.id)
        self.assertEqual(user_profile.realm, internal_realm)

        url = upload_message_attachment(
            "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile, zulip_realm
        )
        # Ensure the correct realm id of the target realm is used instead of the bot's realm.
        self.assertTrue(url.startswith(f"/user_uploads/{zulip_realm.id}/"))

    def test_delete_message_attachment(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        result = self.client_post("/json/user_uploads", {"file": fp})

        response_dict = self.assert_json_success(result)
        path_id = re.sub(r"/user_uploads/", "", response_dict["uri"])

        assert settings.LOCAL_FILES_DIR is not None
        file_path = os.path.join(settings.LOCAL_FILES_DIR, path_id)
        self.assertTrue(os.path.isfile(file_path))

        self.assertTrue(delete_message_attachment(path_id))
        self.assertFalse(os.path.isfile(file_path))

    def test_delete_message_attachments(self) -> None:
        assert settings.LOCAL_UPLOADS_DIR is not None
        assert settings.LOCAL_FILES_DIR is not None

        user_profile = self.example_user("hamlet")
        path_ids = []
        for n in range(1, 1005):
            url = upload_message_attachment(
                "dummy.txt", len(b"zulip!"), "text/plain", b"zulip!", user_profile
            )
            base = "/user_uploads/"
            self.assertEqual(base, url[: len(base)])
            path_id = re.sub(r"/user_uploads/", "", url)
            path_ids.append(path_id)
            file_path = os.path.join(settings.LOCAL_FILES_DIR, path_id)
            self.assertTrue(os.path.isfile(file_path))

        delete_message_attachments(path_ids)
        for path_id in path_ids:
            file_path = os.path.join(settings.LOCAL_FILES_DIR, path_id)
            self.assertFalse(os.path.isfile(file_path))

    def test_all_message_attachments(self) -> None:
        write_local_file("files", "foo", b"content")
        write_local_file("files", "bar/baz", b"content")
        write_local_file("files", "bar/troz", b"content")
        write_local_file("files", "test/other/file", b"content")
        found_files = [r[0] for r in all_message_attachments()]
        self.assertEqual(sorted(found_files), ["bar/baz", "bar/troz", "foo", "test/other/file"])

    def test_avatar_url(self) -> None:
        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            result = self.client_post("/json/users/me/avatar", {"file": image_file})

        response_dict = self.assert_json_success(result)
        self.assertIn("avatar_url", response_dict)
        base = "/user_avatars/"
        url = self.assert_json_success(result)["avatar_url"]
        self.assertEqual(base, url[: len(base)])

        # That URL is accessible when logged out
        self.logout()
        result = self.client_get(url)
        self.assertEqual(result.status_code, 200)

        # We get a resized avatar from it
        image_data = read_test_image_file("img.png")
        resized_avatar = resize_avatar(image_data)
        self.assertEqual(resized_avatar, result.getvalue())

        with self.settings(DEVELOPMENT=False):
            # In production, this is an X-Accel-Redirect to the
            # on-disk content, which nginx serves
            result = self.client_get(url)
            self.assertEqual(result.status_code, 200)
            internal_redirect_path = urlsplit(url).path.replace(
                "/user_avatars/", "/internal/local/user_avatars/"
            )
            self.assertEqual(result["X-Accel-Redirect"], internal_redirect_path)
            self.assertEqual(b"", result.content)

    def test_ensure_avatar_image(self) -> None:
        user_profile = self.example_user("hamlet")
        file_path = user_avatar_path(user_profile)

        write_local_file("avatars", file_path + ".original", read_test_image_file("img.png"))

        assert settings.LOCAL_UPLOADS_DIR is not None
        assert settings.LOCAL_AVATARS_DIR is not None
        image_path = os.path.join(settings.LOCAL_AVATARS_DIR, file_path + ".original")
        with open(image_path, "rb") as f:
            image_data = f.read()

        resized_avatar = resize_avatar(image_data)
        zerver.lib.upload.upload_backend.ensure_avatar_image(user_profile)
        output_path = os.path.join(settings.LOCAL_AVATARS_DIR, file_path + ".png")
        with open(output_path, "rb") as original_file:
            self.assertEqual(resized_avatar, original_file.read())

        resized_avatar = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        zerver.lib.upload.upload_backend.ensure_avatar_image(user_profile, is_medium=True)
        output_path = os.path.join(settings.LOCAL_AVATARS_DIR, file_path + "-medium.png")
        with open(output_path, "rb") as original_file:
            self.assertEqual(resized_avatar, original_file.read())

    def test_get_emoji_url(self) -> None:
        user_profile = self.example_user("hamlet")
        file_name = "emoji.png"

        with get_test_image_file("img.png") as image_file:
            upload_emoji_image(image_file, file_name, user_profile)
        url = zerver.lib.upload.upload_backend.get_emoji_url(file_name, user_profile.realm_id)

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=file_name,
        )
        expected_url = f"/user_avatars/{emoji_path}"
        self.assertEqual(expected_url, url)

        file_name = "emoji.gif"
        with get_test_image_file("animated_img.gif") as image_file:
            upload_emoji_image(image_file, file_name, user_profile)
        url = zerver.lib.upload.upload_backend.get_emoji_url(file_name, user_profile.realm_id)
        still_url = zerver.lib.upload.upload_backend.get_emoji_url(
            file_name, user_profile.realm_id, still=True
        )

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=file_name,
        )

        still_emoji_path = RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_filename_without_extension=os.path.splitext(file_name)[0],
        )
        expected_url = f"/user_avatars/{emoji_path}"
        self.assertEqual(expected_url, url)
        expected_still_url = f"/user_avatars/{still_emoji_path}"
        self.assertEqual(expected_still_url, still_url)

    def test_emoji_upload(self) -> None:
        user_profile = self.example_user("hamlet")
        file_name = "emoji.png"

        with get_test_image_file("img.png") as image_file:
            upload_emoji_image(image_file, file_name, user_profile)

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=file_name,
        )

        assert settings.LOCAL_AVATARS_DIR is not None
        file_path = os.path.join(settings.LOCAL_AVATARS_DIR, emoji_path)
        with open(file_path + ".original", "rb") as original_file:
            self.assertEqual(read_test_image_file("img.png"), original_file.read())

        expected_size = (DEFAULT_EMOJI_SIZE, DEFAULT_EMOJI_SIZE)
        with Image.open(file_path) as resized_image:
            self.assertEqual(expected_size, resized_image.size)

    def test_tarball_upload_and_deletion(self) -> None:
        user_profile = self.example_user("iago")
        self.assertTrue(user_profile.is_realm_admin)

        assert settings.TEST_WORKER_DIR is not None
        tarball_path = os.path.join(settings.TEST_WORKER_DIR, "tarball.tar.gz")
        with open(tarball_path, "w") as f:
            f.write("dummy")

        assert settings.LOCAL_AVATARS_DIR is not None
        url = upload_export_tarball(user_profile.realm, tarball_path)
        self.assertTrue(os.path.isfile(os.path.join(settings.LOCAL_AVATARS_DIR, tarball_path)))

        result = re.search(re.compile(r"([A-Za-z0-9\-_]{24})"), url)
        if result is not None:
            random_name = result.group(1)
        expected_url = f"http://zulip.testserver/user_avatars/exports/{user_profile.realm_id}/{random_name}/tarball.tar.gz"
        self.assertEqual(expected_url, url)

        # Delete the tarball.
        with self.assertLogs(level="WARNING") as warn_log:
            self.assertIsNone(delete_export_tarball("/not_a_file"))
        self.assertEqual(
            warn_log.output,
            ["WARNING:root:not_a_file does not exist. Its entry in the database will be removed."],
        )
        path_id = urlsplit(url).path
        self.assertEqual(delete_export_tarball(path_id), path_id)
