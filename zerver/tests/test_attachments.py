import re
from typing import Any
from unittest import mock

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from analytics.lib.counts import COUNT_STATS, do_fill_count_stat_at_hour
from analytics.models import RealmCount
from zerver.lib.attachments import remove_attachment, user_attachments
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_test_image_file
from zerver.lib.thumbnail import ThumbnailFormat
from zerver.models import Attachment, ImageAttachment


class AttachmentsTests(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        user_profile = self.example_user("cordelia")
        self.attachment = Attachment.objects.create(
            file_name="test.txt",
            path_id="foo/bar/test.txt",
            owner=user_profile,
            realm=user_profile.realm,
            size=512,
        )

    def test_list_by_user(self) -> None:
        user_profile = self.example_user("cordelia")
        self.login_user(user_profile)
        result = self.client_get("/json/attachments")
        response_dict = self.assert_json_success(result)
        attachments = user_attachments(user_profile)
        self.assertEqual(response_dict["attachments"], attachments)

    def test_remove_attachment_exception(self) -> None:
        user_profile = self.example_user("cordelia")
        self.login_user(user_profile)
        with mock.patch(
            "zerver.lib.attachments.delete_message_attachment", side_effect=Exception()
        ):
            result = self.client_delete(f"/json/attachments/{self.attachment.id}")
        self.assert_json_error(
            result, "An error occurred while deleting the attachment. Please try again later."
        )

    @mock.patch("zerver.lib.attachments.delete_message_attachment")
    def test_remove_attachment(self, ignored: Any) -> None:
        user_profile = self.example_user("cordelia")
        self.login_user(user_profile)
        result = self.client_delete(f"/json/attachments/{self.attachment.id}")
        self.assert_json_success(result)
        attachments = user_attachments(user_profile)
        self.assertEqual(attachments, [])

    @mock.patch("zerver.lib.attachments.delete_message_attachment")
    def test_remove_attachment_adjusts_upload_space_snapshot(self, ignored: Any) -> None:
        user_profile = self.example_user("cordelia")
        realm = user_profile.realm
        do_fill_count_stat_at_hour(COUNT_STATS["upload_quota_used_bytes::day"], timezone_now())
        snapshot = RealmCount.objects.get(realm=realm, property="upload_quota_used_bytes::day")
        snapshot_value = snapshot.value
        new_attachment = Attachment.objects.create(
            file_name="new.txt",
            path_id="foo/bar/new.txt",
            owner=user_profile,
            realm=realm,
            size=256,
        )
        used_space = realm.currently_used_upload_space_bytes()

        # self.attachment is counted in the snapshot, so deleting it
        # lowers the snapshot and the used space immediately.
        self.login_user(user_profile)
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.client_delete(f"/json/attachments/{self.attachment.id}")
        self.assert_json_success(result)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.value, snapshot_value - 512)
        self.assertEqual(events[0]["event"]["upload_space_used"], used_space - 512)
        self.assertEqual(realm.currently_used_upload_space_bytes(), used_space - 512)

        # new_attachment was created after the snapshot, so the
        # snapshot is left unchanged.
        result = self.client_delete(f"/json/attachments/{new_attachment.id}")
        self.assert_json_success(result)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.value, snapshot_value - 512)
        self.assertEqual(realm.currently_used_upload_space_bytes(), used_space - 512 - 256)

    @mock.patch("zerver.lib.attachments.delete_message_attachment")
    def test_remove_attachment_deleted_concurrently(self, ignored: Any) -> None:
        user_profile = self.example_user("cordelia")
        do_fill_count_stat_at_hour(COUNT_STATS["upload_quota_used_bytes::day"], timezone_now())
        snapshot = RealmCount.objects.get(
            realm=user_profile.realm, property="upload_quota_used_bytes::day"
        )
        snapshot_value = snapshot.value

        stale_attachment = Attachment.objects.get(id=self.attachment.id)
        remove_attachment(user_profile, self.attachment)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.value, snapshot_value - 512)

        # The second deletion finds no row to delete, so it must not
        # subtract the attachment's size again.
        remove_attachment(user_profile, stale_attachment)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.value, snapshot_value - 512)

    @mock.patch("zerver.lib.attachments.delete_message_attachment")
    def test_remove_imageattachment(self, ignored: Any) -> None:
        self.login_user(self.example_user("hamlet"))
        with (
            self.thumbnail_formats(ThumbnailFormat("webp", 100, 75, animated=True)),
            get_test_image_file("img.png") as image_file,
        ):
            response = self.assert_json_success(
                self.client_post("/json/user_uploads", {"file": image_file})
            )

        path_id = re.sub(r"/user_uploads/", "", response["url"])
        self.assertEqual(Attachment.objects.filter(path_id=path_id).count(), 1)
        self.assertEqual(ImageAttachment.objects.filter(path_id=path_id).count(), 1)
        attachment = Attachment.objects.get(path_id=path_id)
        result = self.client_delete(f"/json/attachments/{attachment.id}")
        self.assert_json_success(result)
        self.assertEqual(Attachment.objects.filter(path_id=path_id).count(), 0)
        self.assertEqual(ImageAttachment.objects.filter(path_id=path_id).count(), 0)

    def test_list_another_user(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        result = self.client_get("/json/attachments")
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["attachments"], [])

    def test_remove_another_user(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        result = self.client_delete(f"/json/attachments/{self.attachment.id}")
        self.assert_json_error(result, "Invalid attachment")
        user_profile_to_remove = self.example_user("cordelia")
        attachments = user_attachments(user_profile_to_remove)
        self.assertEqual(attachments, [self.attachment.to_dict()])

    def test_list_unauthenticated(self) -> None:
        result = self.client_get("/json/attachments")
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", status_code=401
        )

    def test_delete_unauthenticated(self) -> None:
        result = self.client_delete(f"/json/attachments/{self.attachment.id}")
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", status_code=401
        )
