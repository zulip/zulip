# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from django.db.migrations.state import StateApps
from typing_extensions import override

from zerver.lib.test_classes import MigrationsTestCase

# Important note: These tests are very expensive, and details of
# Django's database transaction model mean it does not super work to
# have a lot of migrations tested in this file at once; so we usually
# delete the old migration tests when adding a new one, so this file
# always has a single migration test in it as an example.
#
# The error you get with multiple similar tests doing migrations on
# the same table is this (table name may vary):
#
#   django.db.utils.OperationalError: cannot ALTER TABLE
#   "zerver_subscription" because it has pending trigger events


class StripControlCharactersFromAttachments(MigrationsTestCase):
    migrate_from = "0806_stream_default_push_notifications"
    migrate_to = "0807_strip_control_characters_from_attachments"

    # The migration reports what it repaired, which test-backend
    # otherwise rejects as unexpected console output; pin the counts
    # here, which also verifies that it touches only the dirty rows.
    expected_console_output = """
Stripped control characters from 5 Attachment rows.

Stripped control characters from 1 ArchivedAttachment rows.
"""

    @override
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Attachment = apps.get_model("zerver", "Attachment")
        hamlet = self.example_user("hamlet")
        self.attachment_ids: list[int] = []

        def create_attachment(path_id: str, file_name: str, content_type: str | None) -> int:
            attachment_id = Attachment.objects.create(
                file_name=file_name,
                path_id=path_id,
                owner_id=hamlet.id,
                realm_id=hamlet.realm_id,
                size=6,
                content_type=content_type,
            ).id
            self.attachment_ids.append(attachment_id)
            return attachment_id

        # A trailing newline in either column is the case that makes
        # serve_local() raise BadHeaderError.
        self.bad_file_name_id = create_attachment("1/aa/bb/one.txt", "one.txt\n", "text/plain")
        self.bad_content_type_id = create_attachment("1/aa/bb/two.png", "two.png", "image/png\n")
        # Other control characters are escaped correctly on the way
        # out, but should still be cleaned up.
        self.other_control_id = create_attachment(
            "1/aa/bb/three.txt", "th\x01ree.txt", "text/plain"
        )
        # A NULL content_type must survive the regexp_replace.
        self.null_content_type_id = create_attachment("1/aa/bb/four.txt", "four.txt\n", None)
        # Values which stripping empties get what a new upload would
        # have stored, rather than an empty string.
        self.all_control_id = create_attachment("1/aa/bb/uploaded-file", "\x01.\x02", "\x01")
        # A clean row, as a control.
        self.clean_id = create_attachment("1/aa/bb/five.txt", "five.txt", "text/plain")

        # ArchivedAttachment rows get repaired too, since they can be
        # restored into Attachment.
        ArchivedAttachment = apps.get_model("zerver", "ArchivedAttachment")
        self.archived_id = ArchivedAttachment.objects.create(
            file_name="six.txt\n",
            path_id="1/aa/bb/six.txt",
            owner_id=hamlet.id,
            realm_id=hamlet.realm_id,
            size=6,
            content_type="text/plain\n",
        ).id

    @override
    def tearDown(self) -> None:
        # MigrationsTestCase commits its changes, and its base class
        # asserts that a test leaves the set of rows unchanged, so
        # these have to go before that check runs.
        Attachment = self.apps.get_model("zerver", "Attachment")
        Attachment.objects.filter(id__in=self.attachment_ids).delete()
        ArchivedAttachment = self.apps.get_model("zerver", "ArchivedAttachment")
        ArchivedAttachment.objects.filter(id=self.archived_id).delete()
        super().tearDown()

    def test_control_characters_stripped(self) -> None:
        Attachment = self.apps.get_model("zerver", "Attachment")

        self.assertEqual(Attachment.objects.get(id=self.bad_file_name_id).file_name, "one.txt")
        self.assertEqual(
            Attachment.objects.get(id=self.bad_content_type_id).content_type, "image/png"
        )
        self.assertEqual(Attachment.objects.get(id=self.other_control_id).file_name, "three.txt")

        null_content_type_row = Attachment.objects.get(id=self.null_content_type_id)
        self.assertEqual(null_content_type_row.file_name, "four.txt")
        self.assertIsNone(null_content_type_row.content_type)

        all_control_row = Attachment.objects.get(id=self.all_control_id)
        self.assertEqual(all_control_row.file_name, "uploaded-file")
        self.assertIsNone(all_control_row.content_type)

        clean_row = Attachment.objects.get(id=self.clean_id)
        self.assertEqual(clean_row.file_name, "five.txt")
        self.assertEqual(clean_row.content_type, "text/plain")

        ArchivedAttachment = self.apps.get_model("zerver", "ArchivedAttachment")
        archived_row = ArchivedAttachment.objects.get(id=self.archived_id)
        self.assertEqual(archived_row.file_name, "six.txt")
        self.assertEqual(archived_row.content_type, "text/plain")
