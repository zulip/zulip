# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.
from typing import Optional

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


class MessageEditHistoryTopicEdit(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

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
            subject="migration test 1",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [{"user_id": 11, "timestamp": 1644405030, "prev_subject": "topic test"}]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_topic_edit_only_changes(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        msg = Message.objects.filter(id=self.msg_id).first()
        new_edit_history = msg.edit_history_update_fields

        self.assert_length(new_edit_history, 1)
        self.assertFalse("prev_subject" in new_edit_history[0])
        self.assertEqual(new_edit_history[0]["prev_topic"], "topic test")
        self.assertEqual(new_edit_history[0]["topic"], msg.subject)
        self.assertEqual(
            set(new_edit_history[0].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )


class MessageEditHistoryStreamEdit(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

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
            subject="migration test 2",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [{"user_id": 11, "timestamp": 1644405020, "prev_stream": 3}]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_stream_edit_only_changes(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        Recipient = self.apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id
        new_edit_history = msg.edit_history_update_fields

        self.assert_length(new_edit_history, 1)
        self.assertEqual(new_edit_history[0]["stream"], msg_stream_id)
        self.assertEqual(new_edit_history[0]["stream"], denmark.id)
        self.assertEqual(
            set(new_edit_history[0].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )


class MessageEditHistoryContentEdit(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

    msg_id: Optional[int] = None

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Message = apps.get_model("zerver", "Message")
        Recipient = apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=2, type_id=denmark.id)

        self.msg_id = Message.objects.create(
            recipient_id=denmark_recipient.id,
            subject="migration test 3",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1644405010,
                    "prev_content": "test content edit",
                    "prev_rendered_content": "<p>test content edit</p>",
                    "prev_rendered_content_version": 1,
                }
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_content_only_edit_no_changes(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        msg = Message.objects.filter(id=self.msg_id).first()
        new_edit_history = msg.edit_history_update_fields
        old_edit_history = orjson.loads(msg.edit_history)

        self.assert_length(new_edit_history, 1)
        self.assertEqual(new_edit_history, old_edit_history)


class MessageEditHistoryMultipleEditRecords(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

    msg_id: Optional[int] = None

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Message = apps.get_model("zerver", "Message")
        Recipient = apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=2, type_id=denmark.id)

        self.msg_id = Message.objects.create(
            recipient_id=denmark_recipient.id,
            subject="migration test 4",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1644405040,
                    "prev_content": "second content edit",
                    "prev_rendered_content": "<p>second content edit</p>",
                    "prev_rendered_content_version": 1,
                },
                {"user_id": 11, "timestamp": 1644405030, "prev_subject": "topic test"},
                {"user_id": 11, "timestamp": 1644405020, "prev_stream": 3},
                {
                    "user_id": 11,
                    "timestamp": 1644405010,
                    "prev_content": "test content edit",
                    "prev_rendered_content": "<p>test content edit</p>",
                    "prev_rendered_content_version": 1,
                },
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_multiple_edit_history_entries(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        Recipient = self.apps.get_model("zerver", "Recipient")

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id
        new_edit_history = msg.edit_history_update_fields
        old_edit_history = orjson.loads(msg.edit_history)

        self.assert_length(new_edit_history, 4)
        self.assertEqual(new_edit_history[0], old_edit_history[0])
        self.assertFalse("prev_subject" in new_edit_history[1])
        self.assertTrue("prev_subject" in old_edit_history[1])
        self.assertEqual(new_edit_history[1]["prev_topic"], "topic test")
        self.assertEqual(new_edit_history[1]["topic"], msg.subject)
        self.assertEqual(
            set(new_edit_history[1].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )
        self.assertEqual(new_edit_history[2]["stream"], msg_stream_id)
        self.assertEqual(
            set(new_edit_history[2].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )
        self.assertEqual(new_edit_history[3], old_edit_history[3])


class MessageEditHistoryMultipleStreamTopicEdits(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

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
            subject="migration test 5",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [
                {"user_id": 11, "timestamp": 1644405050, "prev_stream": 3},
                {"user_id": 11, "timestamp": 1644405040, "prev_subject": "topic 3"},
                {
                    "user_id": 11,
                    "timestamp": 1644405030,
                    "prev_stream": 2,
                    "prev_subject": "topic 2",
                },
                {"user_id": 11, "timestamp": 1644405020, "prev_subject": "topic 1"},
                {"user_id": 11, "timestamp": 1644405010, "prev_stream": 1},
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_multiple_stream_and_topic_edits(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        Recipient = self.apps.get_model("zerver", "Recipient")

        msg = Message.objects.filter(id=self.msg_id).first()
        msg_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id
        new_edit_history = msg.edit_history_update_fields

        self.assert_length(new_edit_history, 5)

        self.assertEqual(new_edit_history[0]["stream"], msg_stream_id)
        self.assertEqual(
            set(new_edit_history[0].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )

        self.assertFalse("prev_subject" in new_edit_history[1])
        self.assertEqual(new_edit_history[1]["prev_topic"], "topic 3")
        self.assertEqual(new_edit_history[1]["topic"], msg.subject)
        self.assertEqual(
            set(new_edit_history[1].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )

        self.assertEqual(new_edit_history[2]["stream"], 3)
        self.assertFalse("prev_subject" in new_edit_history[2])
        self.assertEqual(new_edit_history[2]["prev_topic"], "topic 2")
        self.assertEqual(new_edit_history[2]["topic"], "topic 3")
        self.assertEqual(
            set(new_edit_history[2].keys()),
            {"timestamp", "prev_topic", "topic", "user_id", "prev_stream", "stream"},
        )

        self.assertFalse("prev_subject" in new_edit_history[3])
        self.assertEqual(new_edit_history[3]["prev_topic"], "topic 1")
        self.assertEqual(new_edit_history[3]["topic"], "topic 2")
        self.assertEqual(
            set(new_edit_history[3].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )

        self.assertEqual(new_edit_history[4]["stream"], 2)
        self.assertEqual(
            set(new_edit_history[4].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )


class MessageEditAfterMigrationWithEditHistory(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

    msg_id: Optional[int] = None

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Message = apps.get_model("zerver", "Message")
        Recipient = apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=2, type_id=denmark.id)

        self.msg_id = Message.objects.create(
            recipient_id=denmark_recipient.id,
            subject="migration test 6",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1644405020,
                    "prev_stream": 3,
                    "prev_subject": "original topic",
                }
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_msg_with_edit_history_updated_after_migration(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        Recipient = self.apps.get_model("zerver", "Recipient")

        msg = Message.objects.filter(id=self.msg_id).first()
        org_stream_id = Recipient.objects.get(id=msg.recipient_id).type_id
        new_stream = self.make_stream("new stream")

        params_dict = {
            "stream_id": new_stream.id,
            "send_notification_to_old_thread": "false",
            "send_notification_to_new_thread": "false",
        }
        self.login("iago")
        result = self.client_patch(f"/json/messages/{msg.id}", params_dict)
        self.assert_json_success(result)

        old_edit_history = orjson.loads(Message.objects.get(id=self.msg_id).edit_history)
        new_edit_history = Message.objects.get(id=self.msg_id).edit_history_update_fields

        # same number of edits
        self.assert_length(old_edit_history, 2)
        self.assert_length(new_edit_history, 2)

        # new stream field only in BOTH edit historys
        # b/c simulating updates during migration
        self.assertEqual(old_edit_history[0]["prev_stream"], org_stream_id)
        self.assertEqual(new_edit_history[0]["stream"], new_stream.id)
        self.assertEqual(new_edit_history[0]["prev_stream"], org_stream_id)

        self.assertEqual(
            set(old_edit_history[0].keys()), {"timestamp", "prev_stream", "stream", "user_id"}
        )
        self.assertEqual(
            set(new_edit_history[0].keys()),
            {"timestamp", "prev_stream", "stream", "user_id"},
        )

        # updated/new topic and stream fields only in new edit history
        # b/c simulating pre-migration edit_history
        self.assertEqual(old_edit_history[1]["prev_stream"], 3)
        self.assertEqual(old_edit_history[1]["prev_subject"], "original topic")
        self.assertEqual(new_edit_history[1]["stream"], org_stream_id)
        self.assertEqual(new_edit_history[1]["prev_stream"], 3)
        self.assertEqual(new_edit_history[1]["prev_topic"], "original topic")
        self.assertEqual(new_edit_history[1]["topic"], "migration test 6")

        self.assertEqual(
            set(old_edit_history[1].keys()), {"timestamp", "prev_subject", "prev_stream", "user_id"}
        )
        self.assertEqual(
            set(new_edit_history[1].keys()),
            {"timestamp", "prev_topic", "topic", "prev_stream", "stream", "user_id"},
        )


class MessageEditAfterMigrationNoEditHistory(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

    msg_id: Optional[int] = None

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Message = apps.get_model("zerver", "Message")
        Recipient = apps.get_model("zerver", "Recipient")

        iago = self.example_user("iago")
        stream_name = "Denmark"
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=2, type_id=denmark.id)

        self.msg_id = Message.objects.create(
            recipient_id=denmark_recipient.id,
            subject="migration test 7",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

    def test_msg_with_no_edit_history_updated_after_migration(self) -> None:
        Message = self.apps.get_model("zerver", "Message")

        msg = Message.objects.get(id=self.msg_id)

        params_dict = {
            "topic": "new topic",
            "content": "new message content",
            "send_notification_to_old_thread": "false",
            "send_notification_to_new_thread": "false",
        }
        self.login("iago")
        result = self.client_patch(f"/json/messages/{msg.id}", params_dict)
        self.assert_json_success(result)

        # old history data structure has legacy `prev_subject` field
        # AND new topic fields b/c simulating update during migration
        old_edit_history = orjson.loads(Message.objects.get(id=self.msg_id).edit_history)
        self.assert_length(old_edit_history, 1)
        self.assertEqual(old_edit_history[0]["prev_subject"], "migration test 7")
        self.assertEqual(
            set(old_edit_history[0].keys()),
            {
                "timestamp",
                "prev_subject",
                "topic",
                "prev_topic",
                "user_id",
                "prev_content",
                "prev_rendered_content",
                "prev_rendered_content_version",
            },
        )

        # new edit history data structure has updated/new topic fields
        new_edit_history = Message.objects.get(id=self.msg_id).edit_history_update_fields
        self.assert_length(new_edit_history, 1)
        self.assertEqual(new_edit_history[0]["prev_topic"], "migration test 7")
        self.assertEqual(new_edit_history[0]["topic"], "new topic")
        self.assertEqual(
            set(new_edit_history[0].keys()),
            {
                "timestamp",
                "prev_topic",
                "topic",
                "user_id",
                "prev_content",
                "prev_rendered_content",
                "prev_rendered_content_version",
            },
        )

        # content changes are same in both
        self.assertEqual(old_edit_history[0]["prev_content"], new_edit_history[0]["prev_content"])
        self.assertEqual(
            old_edit_history[0]["prev_rendered_content"],
            new_edit_history[0]["prev_rendered_content"],
        )
        self.assertEqual(
            old_edit_history[0]["prev_rendered_content_version"],
            new_edit_history[0]["prev_rendered_content_version"],
        )


class MessageDuringMigration(MigrationsTestCase):
    __unittest_skip__ = False

    migrate_from = "0377_message_edit_history_new_column"
    migrate_to = "0378_message_edit_history_update_fields"

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
            subject="migration test 8",
            sender_id=iago.id,
            sending_client_id=1,
            content="current message text",
            date_sent=timezone_now(),
        ).id

        msg = Message.objects.filter(id=self.msg_id).first()
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1644405030,
                    "prev_subject": "topic test",
                    "prev_topic": "topic test",
                    "topic": "Invalid for test",
                }
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_topic_edit_during_migration(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        msg = Message.objects.get(id=self.msg_id)
        new_edit_history = msg.edit_history_update_fields

        self.assert_length(new_edit_history, 1)
        self.assertFalse("prev_subject" in new_edit_history[0])
        self.assertEqual(new_edit_history[0]["prev_topic"], "topic test")
        self.assertEqual(new_edit_history[0]["topic"], msg.subject)
        self.assertEqual(
            set(new_edit_history[0].keys()), {"timestamp", "prev_topic", "topic", "user_id"}
        )
