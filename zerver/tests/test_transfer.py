from unittest.mock import Mock, patch

from django.conf import settings
from moto import mock_s3

from zerver.lib.actions import check_add_realm_emoji
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import avatar_disk_path, create_s3_buckets, get_test_image_file
from zerver.lib.transfer import (
    transfer_avatars_to_s3,
    transfer_emoji_to_s3,
    transfer_message_files_to_s3,
    transfer_uploads_to_s3,
)
from zerver.lib.upload import resize_emoji, upload_message_file
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

    @mock_s3
    def test_transfer_avatars_to_s3(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]

        self.login('hamlet')
        with get_test_image_file('img.png') as image_file:
            self.client_post("/json/users/me/avatar", {'file': image_file})

        user = self.example_user("hamlet")

        with self.assertLogs(level="INFO"):
            transfer_avatars_to_s3(1)

        path_id = user_avatar_path(user)
        image_key = bucket.Object(path_id)
        original_image_key = bucket.Object(path_id + ".original")
        medium_image_key = bucket.Object(path_id + "-medium.png")

        self.assertEqual(len(list(bucket.objects.all())), 3)
        with open(avatar_disk_path(user), "rb") as f:
            self.assertEqual(image_key.get()['Body'].read(), f.read())
        with open(avatar_disk_path(user, original=True), "rb") as f:
            self.assertEqual(original_image_key.get()['Body'].read(), f.read())
        with open(avatar_disk_path(user, medium=True), "rb") as f:
            self.assertEqual(medium_image_key.get()['Body'].read(), f.read())

    @mock_s3
    def test_transfer_message_files(self) -> None:
        bucket = create_s3_buckets(settings.S3_AUTH_UPLOADS_BUCKET)[0]
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')

        upload_message_file('dummy1.txt', len(b'zulip1!'), 'text/plain', b'zulip1!', hamlet)
        upload_message_file('dummy2.txt', len(b'zulip2!'), 'text/plain', b'zulip2!', othello)

        with self.assertLogs(level="INFO"):
            transfer_message_files_to_s3(1)

        attachments = Attachment.objects.all().order_by("id")

        self.assertEqual(len(list(bucket.objects.all())), 2)
        self.assertEqual(bucket.Object(attachments[0].path_id).get()['Body'].read(), b'zulip1!')
        self.assertEqual(bucket.Object(attachments[1].path_id).get()['Body'].read(), b'zulip2!')

    @mock_s3
    def test_transfer_emoji_to_s3(self) -> None:
        bucket = create_s3_buckets(settings.S3_AVATAR_BUCKET)[0]
        othello = self.example_user('othello')
        RealmEmoji.objects.all().delete()

        emoji_name = "emoji.png"

        with get_test_image_file("img.png") as image_file:
            emoji = check_add_realm_emoji(othello.realm, emoji_name, othello, image_file)
        if not emoji:
            raise AssertionError("Unable to add emoji.")

        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=othello.realm_id,
            emoji_file_name=emoji.file_name,
        )

        with self.assertLogs(level="INFO"):
            transfer_emoji_to_s3(1)

        self.assertEqual(len(list(bucket.objects.all())), 2)
        original_key = bucket.Object(emoji_path + ".original")
        resized_key = bucket.Object(emoji_path)

        with get_test_image_file("img.png") as image_file:
            image_data = image_file.read()
        resized_image_data = resize_emoji(image_data)

        self.assertEqual(image_data, original_key.get()['Body'].read())
        self.assertEqual(resized_image_data, resized_key.get()['Body'].read())
