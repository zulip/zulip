import os
import re
from datetime import datetime, timedelta
from io import StringIO
from typing import Optional

import time_machine
from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.actions.message_delete import do_delete_messages
from zerver.actions.scheduled_messages import check_schedule_message, delete_scheduled_message
from zerver.actions.uploads import do_delete_old_unclaimed_attachments
from zerver.lib.retention import clean_archived_data
from zerver.lib.test_classes import UploadSerializeMixin, ZulipTestCase
from zerver.models import ArchivedAttachment, Attachment, Message, UserProfile
from zerver.models.clients import get_client


class UnclaimedAttachmentTest(UploadSerializeMixin, ZulipTestCase):
    def make_attachment(
        self, filename: str, when: Optional[datetime] = None, uploader: Optional[UserProfile] = None
    ) -> Attachment:
        if when is None:
            when = timezone_now() - timedelta(weeks=2)
        if uploader is None:
            uploader = self.example_user("hamlet")
        self.login_user(uploader)

        with time_machine.travel(when, tick=False):
            file_obj = StringIO("zulip!")
            file_obj.name = filename
            response = self.assert_json_success(
                self.client_post("/json/user_uploads", {"file": file_obj})
            )
            path_id = re.sub(r"/user_uploads/", "", response["uri"])
            return Attachment.objects.get(path_id=path_id)

    def assert_exists(
        self,
        attachment: Attachment,
        *,
        has_file: bool,
        has_attachment: bool,
        has_archived_attachment: bool,
    ) -> None:
        assert settings.LOCAL_FILES_DIR
        self.assertEqual(  # File existence on disk
            os.path.isfile(os.path.join(settings.LOCAL_FILES_DIR, attachment.path_id)), has_file
        )
        self.assertEqual(  # Attachment row
            Attachment.objects.filter(id=attachment.id).exists(), has_attachment
        )
        self.assertEqual(  # ArchivedAttachment row
            ArchivedAttachment.objects.filter(id=attachment.id).exists(), has_archived_attachment
        )

    def test_delete_unused_upload(self) -> None:
        unused_attachment = self.make_attachment("unused.txt")
        self.assert_exists(
            unused_attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

        # If we have 3 weeks of grace, nothing happens
        do_delete_old_unclaimed_attachments(3)
        self.assert_exists(
            unused_attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

        # If we have 1 weeks of grace, the Attachment is deleted, and so is the file on disk
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            unused_attachment, has_file=False, has_attachment=False, has_archived_attachment=False
        )

    def test_delete_used_upload(self) -> None:
        hamlet = self.example_user("hamlet")
        attachment = self.make_attachment("used.txt")

        # Send message referencing that message
        self.subscribe(hamlet, "Denmark")
        body = f"Some files here ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/{attachment.path_id})"
        self.send_stream_message(hamlet, "Denmark", body, "test")

        # Because the message is claimed, it is not removed
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

    def test_delete_upload_archived_message(self) -> None:
        hamlet = self.example_user("hamlet")
        attachment = self.make_attachment("used.txt")

        # Send message referencing that message
        self.subscribe(hamlet, "Denmark")
        body = f"Some files here ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/{attachment.path_id})"
        message_id = self.send_stream_message(hamlet, "Denmark", body, "test")

        # Delete that message; this moves it to ArchivedAttachment but leaves the file on disk
        do_delete_messages(hamlet.realm, [Message.objects.get(id=message_id)])
        self.assert_exists(
            attachment, has_file=True, has_attachment=False, has_archived_attachment=True
        )

        # Removing unclaimed attachments leaves the file, since it is
        # attached to an existing ArchivedAttachment
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=True, has_attachment=False, has_archived_attachment=True
        )

        # Now purge the ArchivedMessage
        with self.settings(ARCHIVED_DATA_VACUUMING_DELAY_DAYS=0):
            clean_archived_data()

        # The attachment still exists as an unclaimed ArchivedAttachment
        self.assert_exists(
            attachment, has_file=True, has_attachment=False, has_archived_attachment=True
        )

        # Removing unclaimed attachments now cleans it out
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=False, has_attachment=False, has_archived_attachment=False
        )

    def test_delete_one_message(self) -> None:
        hamlet = self.example_user("hamlet")
        attachment = self.make_attachment("used.txt")

        # Send message referencing that message
        self.subscribe(hamlet, "Denmark")
        body = f"Some files here ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/{attachment.path_id})"
        first_message_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        second_message_id = self.send_stream_message(hamlet, "Denmark", body, "test")

        # Delete the second message; this leaves an Attachment and an
        # ArchivedAttachment, both associated with a message
        do_delete_messages(hamlet.realm, [Message.objects.get(id=first_message_id)])
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Removing unclaimed attachments leaves the file, since it is
        # attached to an existing Attachment and ArchivedAttachment
        # which have Messages and ArchivedMessages, respectively
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Purging the ArchivedMessage does not affect the Attachment
        # or ArchivedAttachment
        with self.settings(ARCHIVED_DATA_VACUUMING_DELAY_DAYS=0):
            clean_archived_data()
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Removing unclaimed attachments still does nothing, because
        # the ArchivedAttachment is protected by the existing
        # Attachment.
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Deleting the other message now leaves just an ArchivedAttachment
        do_delete_messages(hamlet.realm, [Message.objects.get(id=second_message_id)])
        self.assert_exists(
            attachment, has_file=True, has_attachment=False, has_archived_attachment=True
        )

        # Cleaning out the archived message and purging unclaimed
        # attachments now finally removes it.
        with self.settings(ARCHIVED_DATA_VACUUMING_DELAY_DAYS=0):
            clean_archived_data()
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=False, has_attachment=False, has_archived_attachment=False
        )

    def test_delete_with_scheduled_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        attachment = self.make_attachment("used.txt")

        # Schedule a future send with the attachment
        self.subscribe(hamlet, "Denmark")
        body = f"Some files here ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/{attachment.path_id})"
        scheduled_message_id = check_schedule_message(
            hamlet,
            get_client("website"),
            "stream",
            [self.get_stream_id("Denmark")],
            "Test topic",
            body,
            timezone_now() + timedelta(days=365),
            hamlet.realm,
        )
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

        # The ScheduledMessage protects the attachment from being removed
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

        # Deleting the ScheduledMessage leaves the attachment dangling
        delete_scheduled_message(hamlet, scheduled_message_id)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

        # Having no referents, it is now a target for removal
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=False, has_attachment=False, has_archived_attachment=False
        )

    def test_delete_with_scheduled_message_and_archive(self) -> None:
        hamlet = self.example_user("hamlet")
        attachment = self.make_attachment("used.txt")

        # Schedule a message, and also send one now
        self.subscribe(hamlet, "Denmark")
        body = f"Some files here ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/{attachment.path_id})"
        scheduled_message_id = check_schedule_message(
            hamlet,
            get_client("website"),
            "stream",
            [self.get_stream_id("Denmark")],
            "Test topic",
            body,
            timezone_now() + timedelta(days=365),
            hamlet.realm,
        )
        sent_message_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

        # Deleting the sent message leaves us with an Attachment
        # attached to the scheduled message, and an archived
        # attachment with an archived message
        do_delete_messages(hamlet.realm, [Message.objects.get(id=sent_message_id)])
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Expiring the archived message leaves a dangling
        # ArchivedAttachment and a protected Attachment
        with self.settings(ARCHIVED_DATA_VACUUMING_DELAY_DAYS=0):
            clean_archived_data()
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Removing unclaimed attachments deletes nothing, since the
        # the ArchivedAttachment is protected by the Attachment which
        # is still protected by the scheduled message
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Deleting the ScheduledMessage leaves the attachment fully dangling
        delete_scheduled_message(hamlet, scheduled_message_id)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Having no referents, it is now a target for removal
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=False, has_attachment=False, has_archived_attachment=False
        )

    def test_delete_with_unscheduled_message_and_archive(self) -> None:
        # This is subtly different from the test above -- we delete
        # the scheduled message first, which is the only way to get an
        # Attachment with not referents as well as an
        # ArchivedAttachment which does have references.  Normally,
        # the process of archiving prunes Attachments which have no
        # references.
        hamlet = self.example_user("hamlet")
        attachment = self.make_attachment("used.txt")

        # Schedule a message, and also send one now
        self.subscribe(hamlet, "Denmark")
        body = f"Some files here ...[zulip.txt](http://{hamlet.realm.host}/user_uploads/{attachment.path_id})"
        scheduled_message_id = check_schedule_message(
            hamlet,
            get_client("website"),
            "stream",
            [self.get_stream_id("Denmark")],
            "Test topic",
            body,
            timezone_now() + timedelta(days=365),
            hamlet.realm,
        )
        sent_message_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=False
        )

        # Delete the message and then unschedule the scheduled message
        # before expiring the ArchivedMessages.
        do_delete_messages(hamlet.realm, [Message.objects.get(id=sent_message_id)])
        delete_scheduled_message(hamlet, scheduled_message_id)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Attempting to expire unclaimed attachments leaves the
        # unreferenced Attachment which is protected by the
        # ArchivedAttachment which has archived messages referencing
        # it.
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Expiring archived messages leaves us with a dangling
        # Attachment and ArchivedAttachment, with neither having
        # referents.
        with self.settings(ARCHIVED_DATA_VACUUMING_DELAY_DAYS=0):
            clean_archived_data()
        self.assert_exists(
            attachment, has_file=True, has_attachment=True, has_archived_attachment=True
        )

        # Having no referents in either place, it is now a target for
        # removal
        do_delete_old_unclaimed_attachments(1)
        self.assert_exists(
            attachment, has_file=False, has_attachment=False, has_archived_attachment=False
        )
