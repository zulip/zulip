import os
from unittest.mock import Mock, patch

from django.conf import settings
from moto.core.decorator import mock_aws

from zerver.actions.realm_emoji import check_add_realm_emoji
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    avatar_disk_path,
    create_s3_buckets,
    get_test_image_file,
    read_test_image_file,
)
from zerver.lib.thumbnail import ThumbnailFormat, resize_emoji
from zerver.lib.transfer import (
    transfer_avatars_to_s3,
    transfer_emoji_to_s3,
    transfer_message_files_to_s3,
    transfer_uploads_to_s3,
)
from zerver.lib.upload import upload_message_attachment
from zerver.models import Attachment, RealmEmoji


class TransferUploadsToS3Test(ZulipTestCase):
    @patch("zerver.lib.transfer.transfer_avatars_to_s3")
    @patch("zerver.lib.transfer.transfer_message_files_to_s3")
    @patch("zerver.lib.transfer.transfer_emoji_to_s3")
    def test_transfer_uploads_to_s3(self, m3: Mock, m2: Mock, m1: Mock) -> None:
        transfer_uploads_to_s3(4)

        m1.assert_called_with(4)
        m2.assert_called_with(4)
        m3.assert_called_with(4)

    @mock_aws
    def test_transfer_avatars_to_s3(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        self.login("hamlet")
        with get_test_image_file("img.png") as image_file:
            self.client_post("/json/users/me/avatar", {"file": image_file})

        user = self.example_user("hamlet")

        with self.assertLogs(level="INFO"):
            transfer_avatars_to_s3(1)

        path_id = user_avatar_path(user)
        image_key = bucket.Object(path_id + ".png")
        original_image_key = bucket.Object(path_id + ".original")
        medium_image_key = bucket.Object(path_id + "-medium.png")

        self.assert_length(list(bucket.objects.all()), 3)
        with open(avatar_disk_path(user), "rb") as f:
            self.assertEqual(image_key.get()["Body"].read(), f.read())
        with open(avatar_disk_path(user, original=True), "rb") as f:
            self.assertEqual(original_image_key.get()["Body"].read(), f.read())
        with open(avatar_disk_path(user, medium=True), "rb") as f:
            self.assertEqual(medium_image_key.get()["Body"].read(), f.read())

    @mock_aws
    def test_transfer_message_files(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        upload_message_attachment("dummy1.txt", "text/plain", b"zulip1!", hamlet)
        upload_message_attachment("dummy2.txt", "text/plain", b"zulip2!", othello)
        with (
            self.thumbnail_formats(ThumbnailFormat("webp", 100, 75, animated=False)),
            self.captureOnCommitCallbacks(execute=True),
        ):
            access_path, _ = upload_message_attachment(
                "img.png", "image/png", read_test_image_file("img.png"), hamlet
            )
        self.assertTrue(access_path.startswith("/user_uploads/"))
        image_path_id = access_path.removeprefix("/user_uploads/")
        assert settings.LOCAL_FILES_DIR is not None
        thumbnail_path = os.path.join(
            settings.LOCAL_FILES_DIR, "thumbnail", image_path_id, "100x75.webp"
        )
        self.assertTrue(os.path.exists(thumbnail_path))

        with self.assertLogs(level="INFO"):
            transfer_message_files_to_s3(1)

        attachments = Attachment.objects.all().order_by("id")

        self.assert_length(list(bucket.objects.all()), 4)

        s3_dummy1 = bucket.Object(attachments[0].path_id).get()
        self.assertEqual(s3_dummy1["Body"].read(), b"zulip1!")
        self.assertEqual(
            s3_dummy1["Metadata"],
            {"realm_id": str(attachments[0].realm_id), "user_profile_id": str(hamlet.id)},
        )

        s3_dummy2 = bucket.Object(attachments[1].path_id).get()
        self.assertEqual(s3_dummy2["Body"].read(), b"zulip2!")
        self.assertEqual(
            s3_dummy2["Metadata"],
            {"realm_id": str(attachments[1].realm_id), "user_profile_id": str(othello.id)},
        )

        s3_image = bucket.Object(attachments[2].path_id).get()
        self.assertEqual(
            s3_image["Body"].read(),
            read_test_image_file("img.png"),
        )
        self.assertEqual(
            s3_image["Metadata"],
            {"realm_id": str(attachments[2].realm_id), "user_profile_id": str(hamlet.id)},
        )

        s3_image_thumbnail = bucket.Object(
            os.path.join("thumbnail", attachments[2].path_id, "100x75.webp")
        ).get()
        self.assertEqual(s3_image_thumbnail["Metadata"], {})
        with open(thumbnail_path, "rb") as thumbnail_file:
            self.assertEqual(
                s3_image_thumbnail["Body"].read(),
                thumbnail_file.read(),
            )

    @mock_aws
    def test_transfer_emoji_to_s3(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]
        othello = self.example_user("othello")
        RealmEmoji.objects.all().delete()

        emoji_name = "emoji.png"

        with get_test_image_file("img.png") as image_file:
            emoji = check_add_realm_emoji(
                othello.realm, emoji_name, othello, image_file, "image/png"
            )

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=othello.realm_id,
            emoji_file_name=emoji.file_name,
        )

        with self.assertLogs(level="INFO"):
            transfer_emoji_to_s3(1)

        self.assert_length(list(bucket.objects.all()), 2)
        original_key = bucket.Object(emoji_path + ".original")
        resized_key = bucket.Object(emoji_path)

        image_data = read_test_image_file("img.png")
        resized_image_data, still_image_data = resize_emoji(image_data, "img.png")

        self.assertEqual(still_image_data, None)
        self.assertEqual(image_data, original_key.get()["Body"].read())
        self.assertEqual(resized_image_data, resized_key.get()["Body"].read())

        emoji_name = "emoji2.png"

        with get_test_image_file("animated_img.gif") as image_file:
            emoji = check_add_realm_emoji(
                othello.realm, emoji_name, othello, image_file, "image/gif"
            )

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=othello.realm_id,
            emoji_file_name=emoji.file_name,
        )

        with self.assertLogs(level="INFO"):
            transfer_emoji_to_s3(1)

        self.assert_length(list(bucket.objects.all()), 5)
        original_key = bucket.Object(emoji_path + ".original")
        resized_key = bucket.Object(emoji_path)
        assert emoji.file_name
        still_key = bucket.Object(
            RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
                realm_id=othello.realm_id,
                emoji_filename_without_extension=os.path.splitext(emoji.file_name)[0],
            )
        )

        image_data = read_test_image_file("animated_img.gif")
        resized_image_data, still_image_data = resize_emoji(image_data, "animated_img.gif")

        self.assertEqual(type(still_image_data), bytes)
        self.assertEqual(image_data, original_key.get()["Body"].read())
        self.assertEqual(resized_image_data, resized_key.get()["Body"].read())
        self.assertEqual(still_image_data, still_key.get()["Body"].read())
