# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models, make_client
from django.utils.timezone import now as timezone_now
from django.db.migrations.state import StateApps
from django.db.models.base import ModelBase

from zerver.models import get_stream

class EmojiName2IdTestCase(MigrationsTestCase):

    migrate_from = '0144_remove_realm_create_generic_bot_by_admins_only'
    migrate_to = '0145_reactions_realm_emoji_name_to_id'

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Reaction = apps.get_model('zerver', 'Reaction')
        RealmEmoji = apps.get_model('zerver', 'RealmEmoji')
        Message = apps.get_model('zerver', 'Message')
        Recipient = apps.get_model('zerver', 'Recipient')

        sender = self.example_user('iago')
        realm = sender.realm
        sending_client = make_client(name="test suite")
        stream_name = 'Denmark'
        stream = get_stream(stream_name, realm)
        subject = 'foo'

        def send_fake_message(message_content: str, stream: ModelBase) -> ModelBase:
            recipient = Recipient.objects.get(type_id=stream.id, type=2)
            return Message.objects.create(sender = sender,
                                          recipient = recipient,
                                          subject = subject,
                                          content = message_content,
                                          pub_date = timezone_now(),
                                          sending_client = sending_client)
        message = send_fake_message('Test 1', stream)

        # Create reactions for all the realm emoji's on the message we faked.
        for realm_emoji in RealmEmoji.objects.all():
            reaction = Reaction(user_profile=sender, message=message,
                                emoji_name=realm_emoji.name, emoji_code=realm_emoji.name,
                                reaction_type='realm_emoji')
            reaction.save()
        realm_emoji_reactions_count = Reaction.objects.filter(reaction_type='realm_emoji').count()
        self.assertEqual(realm_emoji_reactions_count, 1)

    def test_tags_migrated(self) -> None:
        """Test runs after the migration, and verifies the data was migrated correctly"""
        Reaction = self.apps.get_model('zerver', 'Reaction')
        RealmEmoji = self.apps.get_model('zerver', 'RealmEmoji')

        realm_emoji_reactions = Reaction.objects.filter(reaction_type='realm_emoji')
        realm_emoji_reactions_count = realm_emoji_reactions.count()
        self.assertEqual(realm_emoji_reactions_count, 1)
        for reaction in realm_emoji_reactions:
            realm_emoji = RealmEmoji.objects.get(
                realm_id=reaction.user_profile.realm_id,
                name=reaction.emoji_name)
            self.assertEqual(reaction.emoji_code, str(realm_emoji.id))
