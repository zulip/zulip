# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models
from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now

from zerver.models import get_realm, get_stream, get_huddle
from zerver.lib.redis_utils import get_redis_client
from zerver.lib.utils import generate_random_token

from typing import Any, Callable, List, Tuple

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

RECIPIENT_PERSONAL = 1
RECIPIENT_STREAM = 2
RECIPIENT_HUDDLE = 3

class SubsNotificationSettingsTestCase(MigrationsTestCase):  # nocoverage

    migrate_from = '0259_missedmessageemailaddress'
    migrate_to = '0260_missed_message_addresses_from_redis_to_db'

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.post_migration_validators = []  # type: List[Callable[[], None]]

        super().__init__(*args, **kwargs)

    def make_redis_entry(self, user_profile_id: int, recipient_id: int, message_topic: str) -> None:
        data = {
            'user_profile_id': user_profile_id,
            'recipient_id': recipient_id,
            'subject': message_topic.encode('utf-8'),
        }

        while True:
            token = generate_random_token(32)
            key = 'missed_message:' + token
            if self.redis_client.hsetnx(key, 'uses_left', 1):
                break

        with self.redis_client.pipeline() as pipeline:
            pipeline.hmset(key, data)
            pipeline.expire(key, 60 * 60 * 24 * 5)
            pipeline.execute()

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        self.redis_client = get_redis_client()
        # To ensure a predictable state for the test, we need to clear out all the
        # redis keys that could interfere:
        for key in self.redis_client.keys("missed_message:*"):
            self.redis_client.delete(key)

        Recipient = apps.get_model('zerver', 'Recipient')
        Message = apps.get_model('zerver', 'Message')
        Client = apps.get_model('zerver', 'Client')
        MissedMessageEmailAddress = apps.get_model('zerver', 'MissedMessageEmailAddress')

        def _make_message(sender_id: int, recipient_id: int, topic: str='') -> Any:
            (sending_client, _) = Client.objects.get_or_create(name='test_migations')
            return Message.objects.create(sender_id=sender_id, recipient_id=recipient_id,
                                          subject=topic, content='test message',
                                          date_sent=timezone_now(), sending_client_id=sending_client.id)

        def make_personal_message(sender_id: int, receiver_id: int) -> Any:
            recipient = Recipient.objects.get(type=RECIPIENT_PERSONAL, type_id=receiver_id)
            return _make_message(sender_id, recipient.id)

        def make_stream_message(sender_id: int, receiver_id: int, topic: str) -> Any:
            recipient = Recipient.objects.get(type=RECIPIENT_STREAM, type_id=receiver_id)
            return _make_message(sender_id, recipient.id, topic)

        def make_huddle_message(sender_id: int, receiver_ids: List[int]) -> Tuple[Any, Any]:
            """
            This function also returns the recipient object, for the calling code to use for
            putting the appropriate missed message address entry into redis, without having
            to duplicate the effort of fetching it.
            """

            assert sender_id in receiver_ids
            assert len(receiver_ids) > 2
            huddle = get_huddle(receiver_ids)

            recipient = Recipient.objects.get(type=RECIPIENT_HUDDLE, type_id=huddle.id)
            return _make_message(sender_id, recipient.id), recipient

        realm = get_realm("zulip")
        iago = self.example_user('iago')
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        aaron = self.example_user('aaron')

        denmark = get_stream("Denmark", realm)
        scotland = get_stream("Scotland", realm)
        rome = get_stream("Rome", realm)

        msg_success_personal = make_personal_message(iago.id, hamlet.id)
        self.make_redis_entry(hamlet.id, iago.recipient.id, '')

        def validator_success_personal() -> None:
            mm_address = MissedMessageEmailAddress.objects.get(message_id=msg_success_personal.id)
            self.assertEqual(mm_address.user_profile_id, hamlet.id)

        msg_success_stream = make_stream_message(iago.id, denmark.id, "msg_success_stream")
        self.make_redis_entry(othello.id, denmark.recipient.id, "msg_success_stream")

        def validator_success_stream() -> None:
            mm_address = MissedMessageEmailAddress.objects.get(message_id=msg_success_stream.id)
            self.assertEqual(mm_address.user_profile_id, othello.id)

        msg_huddle_success, huddle_recipient = make_huddle_message(iago.id, [iago.id, hamlet.id, othello.id])
        self.make_redis_entry(hamlet.id, huddle_recipient.id, '')

        def validator_success_huddle() -> None:
            mm_address = MissedMessageEmailAddress.objects.get(message_id=msg_huddle_success.id)
            self.assertEqual(mm_address.user_profile_id, hamlet.id)

        # Now we simulate various cases with objects missing from the database:

        msg_user_missing = make_stream_message(iago.id, denmark.id, "msg_user_missing")
        self.make_redis_entry(aaron.id, denmark.recipient.id, "msg_user_missing")
        aaron.delete()

        def validator_user_missing() -> None:
            self.assertFalse(
                MissedMessageEmailAddress.objects.filter(message_id=msg_user_missing.id).exists()
            )

        msg_recipient_missing_id = make_stream_message(iago.id, scotland.id, "msg_recipient_missing").id
        self.make_redis_entry(hamlet.id, scotland.recipient.id, "msg_recipient_missing")
        scotland.recipient.delete()

        def validator_recipient_missing() -> None:
            self.assertFalse(
                MissedMessageEmailAddress.objects.filter(message_id=msg_recipient_missing_id).exists()
            )

        msg_topic_missing = make_stream_message(iago.id, rome.id, "msg_topic_missing")
        msg_topic_missing_id = msg_topic_missing.id
        cordelia = self.example_user('cordelia')
        self.make_redis_entry(cordelia.id, rome.recipient.id, "msg_topic_missing")
        msg_topic_missing.delete()

        def validator_topic_missing() -> None:
            # If the original topic no longer exists, no mm address should
            # be created.
            self.assertFalse(
                MissedMessageEmailAddress.objects.filter(
                    message_id=msg_topic_missing_id).exists()
            )
            self.assertFalse(MissedMessageEmailAddress.objects.filter(user_profile_id=cordelia.id).exists())

        prospero = self.example_user("prospero")
        msg_personal_no_messages = make_personal_message(hamlet.id, prospero.id)
        msg_personal_no_messages_id = msg_personal_no_messages.id
        self.make_redis_entry(prospero.id, hamlet.recipient.id, "")
        # Delete all messages from hamlet to prospero:
        Message.objects.filter(sender_id=hamlet.id, recipient_id=prospero.recipient_id).delete()

        def validator_personal_no_messages() -> None:
            # If no messages from hamlet to prospero exist, no mm address should
            # be created.
            self.assertFalse(
                MissedMessageEmailAddress.objects.filter(
                    message_id=msg_personal_no_messages_id).exists()
            )
            self.assertFalse(MissedMessageEmailAddress.objects.filter(user_profile_id=prospero.id).exists())

        polonius = self.example_user("polonius")
        msg_huddle_no_messages, huddle_recipient = make_huddle_message(iago.id, [iago.id, hamlet.id, polonius.id])
        msg_huddle_no_messages_id = msg_huddle_no_messages.id
        self.make_redis_entry(polonius.id, huddle_recipient.id, '')
        # Delete all messages from hamlet to the huddle:
        Message.objects.filter(recipient_id=huddle_recipient.id).delete()

        def validator_huddle_no_messages() -> None:
            # If no messages from hamlet to the huddle exist, no mm address should
            # be created.
            self.assertFalse(
                MissedMessageEmailAddress.objects.filter(
                    message_id=msg_huddle_no_messages_id).exists()
            )
            self.assertFalse(MissedMessageEmailAddress.objects.filter(user_profile_id=polonius.id).exists())

        self.post_migration_validators = [validator_success_personal, validator_success_stream, validator_success_huddle,
                                          validator_user_missing, validator_recipient_missing,
                                          validator_topic_missing,
                                          validator_personal_no_messages, validator_huddle_no_messages]

    def test_subs_migrated(self) -> None:
        for validator in self.post_migration_validators:
            validator()
