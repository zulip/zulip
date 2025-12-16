from unittest import mock
from django.core.management import call_command
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile, Subscription, Recipient, Message
from zerver.models.realms import get_realm

class TestSuggestChannelUnsubscribes(ZulipTestCase):
    def test_suggest_channel_unsubscribes(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        
        # Subscribe user to many streams
        self.subscribe(user, "Denmark")
        self.subscribe(user, "Scotland")
        self.subscribe(user, "Verona")
        
        # By default threshold is 30, so with 3 subs nothing should happen
        with mock.patch("zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message") as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=30)
            mock_send.assert_not_called()

        # Set threshold to 2, should trigger
        with mock.patch("zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message") as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=2)
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            # self.assertEqual(args[0], realm) # realm
            # self.assertEqual(args[2], user) # recipient
            # self.assertIn("subscribed to 3 channels", args[3]) # content

    def test_avoid_duplicate_suggestions(self) -> None:
        user = self.example_user("hamlet")
        self.subscribe(user, "Denmark")
        self.subscribe(user, "Scotland")
        self.subscribe(user, "Verona")

        # First run triggers
        with mock.patch("zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message") as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=2)
            mock_send.assert_called_once()
        
        # Simulate message sent
        from zerver.models.users import get_system_bot
        from django.conf import settings
        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, user.realm.id)
        self.send_personal_message(notification_bot, user, content="... #channels/recommendations ...")

        # Second run should NOT trigger
        with mock.patch("zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message") as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=2)
            mock_send.assert_not_called()
