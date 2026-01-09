from datetime import timedelta
from unittest.mock import patch

from django.utils.timezone import now as timezone_now

from zerver.actions.bot_presence import do_update_bot_presence
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserPresence


class BotPresenceTests(ZulipTestCase):
    def test_do_update_bot_presence_connect(self) -> None:
        """Test that connecting a bot creates/updates presence with correct timestamp."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        # Connect the bot
        log_time = timezone_now()
        do_update_bot_presence(bot, is_connected=True, log_time=log_time)

        presence = UserPresence.objects.get(user_profile=bot)
        # When connected, last_active_time should be set
        self.assertIsNotNone(presence.last_active_time)
        self.assertEqual(presence.last_connected_time, log_time)
        self.assertEqual(presence.realm_id, bot.realm_id)

    def test_do_update_bot_presence_disconnect_clears_active_time(self) -> None:
        """Test that disconnecting a bot clears last_active_time but preserves last_connected_time."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        # First connect
        connect_time = timezone_now()
        do_update_bot_presence(bot, is_connected=True, log_time=connect_time)

        # Then disconnect - should clear last_active_time
        disconnect_time = connect_time + timedelta(hours=1)
        do_update_bot_presence(bot, is_connected=False, log_time=disconnect_time)

        presence = UserPresence.objects.get(user_profile=bot)
        # last_active_time should be None (disconnected)
        self.assertIsNone(presence.last_active_time)
        # last_connected_time should be updated to disconnect time
        self.assertEqual(presence.last_connected_time, disconnect_time)

    def test_do_update_bot_presence_reconnect_updates_timestamp(self) -> None:
        """Test that reconnecting updates timestamps."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        # First connect
        first_connect_time = timezone_now()
        do_update_bot_presence(bot, is_connected=True, log_time=first_connect_time)

        # Disconnect
        do_update_bot_presence(bot, is_connected=False)

        # Reconnect with new timestamp
        second_connect_time = first_connect_time + timedelta(hours=2)
        do_update_bot_presence(bot, is_connected=True, log_time=second_connect_time)

        presence = UserPresence.objects.get(user_profile=bot)
        self.assertIsNotNone(presence.last_active_time)
        self.assertEqual(presence.last_connected_time, second_connect_time)

    def test_do_update_bot_presence_non_bot_raises(self) -> None:
        """Test that calling with non-bot user raises ValueError."""
        user = self.example_user("hamlet")
        self.assertFalse(user.is_bot)

        with self.assertRaises(ValueError) as cm:
            do_update_bot_presence(user, is_connected=True)

        self.assertIn("non-bot user", str(cm.exception))


class BotPresenceAPITests(ZulipTestCase):
    def test_update_bot_presence_api(self) -> None:
        """Test the bot presence API endpoint."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        # Set bot as connected
        result = self.api_post(
            bot,
            "/api/v1/bots/me/presence",
            {"is_connected": "true"},
        )
        self.assert_json_success(result)

        presence = UserPresence.objects.get(user_profile=bot)
        # Connected bots have last_active_time set
        self.assertIsNotNone(presence.last_active_time)

    def test_update_bot_presence_api_disconnect(self) -> None:
        """Test disconnecting via API."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        # First connect
        self.api_post(bot, "/api/v1/bots/me/presence", {"is_connected": "true"})

        # Then disconnect
        result = self.api_post(
            bot,
            "/api/v1/bots/me/presence",
            {"is_connected": "false"},
        )
        self.assert_json_success(result)

        presence = UserPresence.objects.get(user_profile=bot)
        # Disconnected bots have last_active_time = None
        self.assertIsNone(presence.last_active_time)

    def test_update_bot_presence_api_non_bot_rejected(self) -> None:
        """Test that non-bots cannot use the bot presence endpoint."""
        user = self.example_user("hamlet")
        self.assertFalse(user.is_bot)

        result = self.api_post(
            user,
            "/api/v1/bots/me/presence",
            {"is_connected": "true"},
        )
        self.assert_json_error(result, "This endpoint is only for bots.")


class BotPresenceEventTests(ZulipTestCase):
    """Tests for bot presence events using the unified presence system."""

    def test_do_update_bot_presence_broadcasts_event(self) -> None:
        """Test that updating bot presence broadcasts a presence event."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        with patch(
            "zerver.actions.presence.send_presence_changed"
        ) as mock_send_presence:
            # captureOnCommitCallbacks ensures on_commit callbacks run during test
            with self.captureOnCommitCallbacks(execute=True):
                do_update_bot_presence(bot, is_connected=True)

            # The function is called via transaction.on_commit
            mock_send_presence.assert_called_once()
            call_args = mock_send_presence.call_args
            called_user = call_args[0][0]
            called_presence = call_args[0][1]

            self.assertEqual(called_user.id, bot.id)
            # When connected, last_active_time should be set
            self.assertIsNotNone(called_presence.last_active_time)
