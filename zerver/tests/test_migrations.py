# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from typing import Optional
from unittest import skip

import orjson
from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models
from zerver.models import get_stream

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
#
# As a result, we generally mark these tests as skipped once they have
# been tested for a migration being merged.


@skip("Will not pass once newer migrations are merged.")  # nocoverage # skipped
class MessageEditHistoryLegacyFormats(MigrationsTestCase):
    migrate_from = "0376_set_realmemoji_author_and_reupload_realmemoji"
    migrate_to = "0377_message_edit_history_format"

    msg_id: Optional[int] = None

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Recipient = apps.get_model("zerver", "Recipient")
        Message = apps.get_model("zerver", "Message")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=2, type_id=denmark.id)

        self.msg_id = Message.objects.create(
            recipient_id=denmark_recipient.id,
            subject="topic 4",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        # topic edits contain only "prev_subject" field.
        # stream edits contain only "prev_stream" field.
        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1644405050,
                    "prev_stream": 3,
                    "prev_subject": "topic 3",
                },
                {"user_id": 11, "timestamp": 1644405040, "prev_stream": 2},
                {
                    "user_id": 11,
                    "timestamp": 1644405030,
                    "prev_content": "test content and topic edit",
                    "prev_rendered_content": "<p>test content and topic edit</p>",
                    "prev_rendered_content_version": 1,
                    "prev_subject": "topic 2",
                },
                {"user_id": 11, "timestamp": 1644405020, "prev_subject": "topic 1"},
                {
                    "user_id": 11,
                    "timestamp": 1644405010,
                    "prev_content": "test content only edit",
                    "prev_rendered_content": "<p>test content only edit</p>",
                    "prev_rendered_content_version": 1,
                },
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_message_legacy_edit_history_format(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        Recipient = self.apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id
        new_edit_history = orjson.loads(msg.edit_history)

        self.assert_length(new_edit_history, 5)

        # stream and topic edit entry
        self.assertFalse("prev_subject" in new_edit_history[0])
        self.assertEqual(new_edit_history[0]["prev_topic"], "topic 3")
        self.assertEqual(new_edit_history[0]["topic"], msg.subject)
        self.assertEqual(new_edit_history[0]["prev_stream"], 3)
        self.assertEqual(new_edit_history[0]["stream"], msg_stream_id)
        self.assertEqual(new_edit_history[0]["stream"], denmark.id)
        self.assertEqual(
            set(new_edit_history[0].keys()),
            {"timestamp", "prev_topic", "topic", "prev_stream", "stream", "user_id"},
        )

        # stream only edit entry
        self.assertEqual(new_edit_history[1]["prev_stream"], 2)
        self.assertEqual(new_edit_history[1]["stream"], 3)
        self.assertEqual(
            set(new_edit_history[1].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )

        # topic and content edit entry
        self.assertFalse("prev_subject" in new_edit_history[2])
        self.assertEqual(new_edit_history[2]["prev_topic"], "topic 2")
        self.assertEqual(new_edit_history[2]["topic"], "topic 3")
        self.assertEqual(new_edit_history[2]["prev_content"], "test content and topic edit")
        self.assertEqual(
            new_edit_history[2]["prev_rendered_content"], "<p>test content and topic edit</p>"
        )
        self.assertEqual(new_edit_history[2]["prev_rendered_content_version"], 1)
        self.assertEqual(
            set(new_edit_history[2].keys()),
            {
                "timestamp",
                "prev_topic",
                "topic",
                "prev_content",
                "prev_rendered_content",
                "prev_rendered_content_version",
                "user_id",
            },
        )

        # topic only edit entry
        self.assertFalse("prev_subject" in new_edit_history[3])
        self.assertEqual(new_edit_history[3]["prev_topic"], "topic 1")
        self.assertEqual(new_edit_history[3]["topic"], "topic 2")
        self.assertEqual(
            set(new_edit_history[3].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )

        # content only edit entry - not retested because never changes
        self.assertEqual(new_edit_history[4]["prev_content"], "test content only edit")
        self.assertEqual(
            new_edit_history[4]["prev_rendered_content"], "<p>test content only edit</p>"
        )
        self.assertEqual(new_edit_history[4]["prev_rendered_content_version"], 1)
        self.assertEqual(
            set(new_edit_history[4].keys()),
            {
                "timestamp",
                "prev_content",
                "prev_rendered_content",
                "prev_rendered_content_version",
                "user_id",
            },
        )


@skip("Will not pass once newer migrations are merged.")  # nocoverage # skipped
class MessageEditHistoryModernFormats(MigrationsTestCase):
    migrate_from = "0376_set_realmemoji_author_and_reupload_realmemoji"
    migrate_to = "0377_message_edit_history_format"

    msg_id: Optional[int] = None

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Recipient = apps.get_model("zerver", "Recipient")
        Message = apps.get_model("zerver", "Message")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=2, type_id=denmark.id)

        self.msg_id = Message.objects.create(
            recipient_id=denmark_recipient.id,
            subject="topic 4",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id

        # topic edits contain "topic" and "prev_topic" fields.
        # stream edits contain "stream" and "prev_stream" fields.
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1644405050,
                    "stream": msg_stream_id,
                    "prev_stream": 3,
                    "topic": msg.subject,
                    "prev_topic": "topic 3",
                },
                {"user_id": 11, "timestamp": 1644405040, "prev_stream": 2, "stream": 3},
                {
                    "user_id": 11,
                    "timestamp": 1644405030,
                    "prev_content": "test content and topic edit",
                    "prev_rendered_content": "<p>test content and topic edit</p>",
                    "prev_rendered_content_version": 1,
                    "prev_topic": "topic 2",
                    "topic": "topic 3",
                },
                {
                    "user_id": 11,
                    "timestamp": 1644405020,
                    "prev_topic": "topic 1",
                    "topic": "topic 2",
                },
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_message_modern_edit_history_format(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        Recipient = self.apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id
        new_edit_history = orjson.loads(msg.edit_history)

        self.assert_length(new_edit_history, 4)

        # stream and topic edit entry
        self.assertEqual(new_edit_history[0]["prev_topic"], "topic 3")
        self.assertEqual(new_edit_history[0]["topic"], msg.subject)
        self.assertEqual(new_edit_history[0]["prev_stream"], 3)
        self.assertEqual(new_edit_history[0]["stream"], msg_stream_id)
        self.assertEqual(new_edit_history[0]["stream"], denmark.id)
        self.assertEqual(
            set(new_edit_history[0].keys()),
            {"timestamp", "prev_topic", "topic", "prev_stream", "stream", "user_id"},
        )

        # stream only edit entry
        self.assertEqual(new_edit_history[1]["prev_stream"], 2)
        self.assertEqual(new_edit_history[1]["stream"], 3)
        self.assertEqual(
            set(new_edit_history[1].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )

        # topic and content edit entry
        self.assertEqual(new_edit_history[2]["prev_topic"], "topic 2")
        self.assertEqual(new_edit_history[2]["topic"], "topic 3")
        self.assertEqual(new_edit_history[2]["prev_content"], "test content and topic edit")
        self.assertEqual(
            new_edit_history[2]["prev_rendered_content"], "<p>test content and topic edit</p>"
        )
        self.assertEqual(new_edit_history[2]["prev_rendered_content_version"], 1)
        self.assertEqual(
            set(new_edit_history[2].keys()),
            {
                "timestamp",
                "prev_topic",
                "topic",
                "prev_content",
                "prev_rendered_content",
                "prev_rendered_content_version",
                "user_id",
            },
        )

        # topic only edit entry
        self.assertEqual(new_edit_history[3]["prev_topic"], "topic 1")
        self.assertEqual(new_edit_history[3]["topic"], "topic 2")
        self.assertEqual(
            set(new_edit_history[3].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )


@skip("Will not pass once newer migrations are merged.")  # nocoverage # skipped
class MessageEditHistoryIntermediateFormats(MigrationsTestCase):
    migrate_from = "0376_set_realmemoji_author_and_reupload_realmemoji"
    migrate_to = "0377_message_edit_history_format"

    msg_id: Optional[int] = None

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Recipient = apps.get_model("zerver", "Recipient")
        Message = apps.get_model("zerver", "Message")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=2, type_id=denmark.id)

        self.msg_id = Message.objects.create(
            recipient_id=denmark_recipient.id,
            subject="topic 4",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id

        # topic edits contain "prev_subject", "topic" and "prev_topic" fields.
        # stream edits contain "stream" and "prev_stream" fields.
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1644405050,
                    "stream": msg_stream_id,
                    "prev_stream": 3,
                    "topic": msg.subject,
                    "prev_topic": "topic 3",
                    "prev_subject": "topic 3",
                },
                {"user_id": 11, "timestamp": 1644405040, "prev_stream": 2, "stream": 3},
                {
                    "user_id": 11,
                    "timestamp": 1644405030,
                    "prev_content": "test content and topic edit",
                    "prev_rendered_content": "<p>test content and topic edit</p>",
                    "prev_rendered_content_version": 1,
                    "prev_topic": "topic 2",
                    "prev_subject": "topic 2",
                    "topic": "topic 3",
                },
                {
                    "user_id": 11,
                    "timestamp": 1644405020,
                    "prev_topic": "topic 1",
                    "prev_subject": "topic 1",
                    "topic": "topic 2",
                },
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_message_temporary_edit_history_format(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        Recipient = self.apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id
        new_edit_history = orjson.loads(msg.edit_history)

        self.assert_length(new_edit_history, 4)

        # stream and topic edit entry
        self.assertFalse("prev_subject" in new_edit_history[0])
        self.assertEqual(new_edit_history[0]["prev_topic"], "topic 3")
        self.assertEqual(new_edit_history[0]["topic"], msg.subject)
        self.assertEqual(new_edit_history[0]["prev_stream"], 3)
        self.assertEqual(new_edit_history[0]["stream"], msg_stream_id)
        self.assertEqual(new_edit_history[0]["stream"], denmark.id)
        self.assertEqual(
            set(new_edit_history[0].keys()),
            {"timestamp", "prev_topic", "topic", "prev_stream", "stream", "user_id"},
        )

        # stream only edit entry
        self.assertEqual(new_edit_history[1]["prev_stream"], 2)
        self.assertEqual(new_edit_history[1]["stream"], 3)
        self.assertEqual(
            set(new_edit_history[1].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )

        # topic and content edit entry
        self.assertFalse("prev_subject" in new_edit_history[2])
        self.assertEqual(new_edit_history[2]["prev_topic"], "topic 2")
        self.assertEqual(new_edit_history[2]["topic"], "topic 3")
        self.assertEqual(new_edit_history[2]["prev_content"], "test content and topic edit")
        self.assertEqual(
            new_edit_history[2]["prev_rendered_content"], "<p>test content and topic edit</p>"
        )
        self.assertEqual(new_edit_history[2]["prev_rendered_content_version"], 1)
        self.assertEqual(
            set(new_edit_history[2].keys()),
            {
                "timestamp",
                "prev_topic",
                "topic",
                "prev_content",
                "prev_rendered_content",
                "prev_rendered_content_version",
                "user_id",
            },
        )

        # topic only edit entry
        self.assertFalse("prev_subject" in new_edit_history[3])
        self.assertEqual(new_edit_history[3]["prev_topic"], "topic 1")
        self.assertEqual(new_edit_history[3]["topic"], "topic 2")
        self.assertEqual(
            set(new_edit_history[3].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )
