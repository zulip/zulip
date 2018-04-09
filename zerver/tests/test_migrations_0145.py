from zerver.lib.test_classes import (
    MigrationsTestCase,
)
from django.utils.timezone import now as timezone_now
from django.db.migrations.state import StateApps
from django.db.models.base import ModelBase

class EmojiName2IdTestCase(MigrationsTestCase):

    migrate_from = '0144_remove_realm_create_generic_bot_by_admins_only'
    migrate_to = '0145_reactions_realm_emoji_name_to_id'

    def setUpBeforeMigration(self, apps: StateApps) -> None:
        UserProfile = apps.get_model('zerver', 'UserProfile')
        Reaction = apps.get_model('zerver', 'Reaction')
        RealmEmoji = apps.get_model('zerver', 'RealmEmoji')
        Stream = apps.get_model('zerver', 'Stream')
        Message = apps.get_model('zerver', 'Message')
        Recipient = apps.get_model('zerver', 'Recipient')
        Realm = apps.get_model('zerver', 'Realm')
        Client = apps.get_model('zerver', 'Client')

        realm = Realm.objects.get(string_id='zulip')
        sender = UserProfile.objects.select_related().get(email__iexact='iago@zulip.com'.strip(), realm=realm)
        sending_client, _ = Client.objects.get_or_create(name="test suite")
        stream_name = 'Denmark'
        stream = Stream.objects.select_related("realm").get(
            name__iexact=stream_name.strip(), realm_id=realm.id)
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

        for realm_emoji in RealmEmoji.objects.all():
            reaction = Reaction(user_profile=sender, message=message,
                                emoji_name=realm_emoji.name, emoji_code=realm_emoji.name,
                                reaction_type='realm_emoji')
            reaction.save()

    def test_tags_migrated(self) -> None:
        Reaction = self.apps.get_model('zerver', 'Reaction')
        RealmEmoji = self.apps.get_model('zerver', 'RealmEmoji')
        for reaction in Reaction.objects.filter(reaction_type='realm_emoji'):
            realm_emoji = RealmEmoji.objects.get(
                realm_id=reaction.user_profile.realm_id,
                name=reaction.emoji_name)
            self.assertEqual(reaction.emoji_code, str(realm_emoji.id))
