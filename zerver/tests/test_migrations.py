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


class EditHistoryMigrationTest(MigrationsTestCase):
    migrate_from = "0478_add_edit_history_entries"
    migrate_to = "0479_backfill_edit_history"

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
            subject="testing migration",
            sender_id=iago.id,
            sending_client_id=1,
            content="whatever",
            date_sent=timezone_now(),
            realm_id=iago.realm_id,
        ).id

        msg = Message.objects.get(id=self.msg_id)
        msg.edit_history = orjson.dumps(
            [
                {
                    "user_id": 11,
                    "timestamp": 1618597518,
                    "prev_content": "test msg",
                    "prev_rendered_content": "<p>test msg</p>",
                    "prev_rendered_content_version": 1,
                }
            ]
        ).decode()
        msg.save(update_fields=["edit_history"])

    def test_backfill_edit_message_array(self) -> None:
        Message = self.apps.get_model("zerver", "Message")
        msg = Message.objects.filter(id=self.msg_id).first()
        edit_history = orjson.loads(msg.edit_history)
        self.assertListEqual(msg.edit_history_entries, edit_history)
