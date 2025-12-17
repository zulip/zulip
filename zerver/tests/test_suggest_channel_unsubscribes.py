from unittest import mock

from django.core.management import call_command

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message


class TestSuggestChannelUnsubscribes(ZulipTestCase):
    def test_suggest_channel_unsubscribes(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm

        # Subscribe user to many streams
        # High threshold to avoid picking up default fixture users (max ~7 subs)
        threshold = 20
        for i in range(threshold + 1):
            self.subscribe(user, f"stream{i}")

        # By default threshold is 30, so with 21 subs nothing should happen
        with mock.patch(
            "zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message"
        ) as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=30)
            mock_send.assert_not_called()

        # Set threshold to 20, should trigger
        with mock.patch(
            "zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message"
        ) as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=20)
            mock_send.assert_called_once()
            _, kwargs = mock_send.call_args
            self.assertEqual(kwargs["realm"], realm)  # realm
            self.assertEqual(kwargs["recipient"], user)  # recipient
            self.assertIn("subscribed to", kwargs["content"])  # content
            self.assertIn("#channels/recommendations", kwargs["content"])

    def test_avoid_duplicate_suggestions(self) -> None:
        user = self.example_user("hamlet")

        threshold = 20
        for i in range(threshold + 1):
            self.subscribe(user, f"stream{i}")

        # First run triggers
        with mock.patch(
            "zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message"
        ) as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=20)
            mock_send.assert_called_once()

        # Simulate message sent - create manually to avoid realm/validation issues with system bot helpers
        from django.conf import settings
        from django.utils.timezone import now

        from zerver.models.users import get_system_bot

        notification_bot = get_system_bot(settings.NOTIFICATION_BOT, user.realm.id)

        Message.objects.create(
            sender=notification_bot,
            recipient=user.recipient,
            content="... #channels/recommendations ...",
            date_sent=now(),
            realm=user.realm,
            sending_client_id=1,  # arbitrary
        )

        # Second run should NOT trigger
        with mock.patch(
            "zerver.management.commands.suggest_channel_unsubscribes.internal_send_private_message"
        ) as mock_send:
            call_command("suggest_channel_unsubscribes", threshold=20)
            mock_send.assert_not_called()
