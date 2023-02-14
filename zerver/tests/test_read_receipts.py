import orjson
from django.utils.timezone import now as timezone_now

from zerver.actions.create_user import do_reactivate_user
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import do_deactivate_user
from zerver.lib.muted_users import add_user_mute, get_mute_object
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserMessage, UserProfile


class TestReadReceipts(ZulipTestCase):
    def mark_message_read(self, user: UserProfile, message_id: int) -> None:
        result = self.api_post(
            user,
            "/api/v1/messages/flags",
            {"messages": orjson.dumps([message_id]).decode(), "op": "add", "flag": "read"},
        )
        self.assert_json_success(result)

    def test_stream_message(self) -> None:
        hamlet = self.example_user("hamlet")
        sender = self.example_user("othello")

        message_id = self.send_stream_message(sender, "Verona", "read receipts")
        self.login("hamlet")

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id not in result.json()["user_ids"])

        self.mark_message_read(hamlet, message_id)

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id in result.json()["user_ids"])
        self.assertTrue(sender.id not in result.json()["user_ids"])

    def test_personal_message(self) -> None:
        hamlet = self.example_user("hamlet")
        sender = self.example_user("othello")

        message_id = self.send_personal_message(sender, hamlet)
        self.login("hamlet")

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id not in result.json()["user_ids"])

        self.mark_message_read(hamlet, message_id)

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id in result.json()["user_ids"])
        self.assertTrue(sender.id not in result.json()["user_ids"])

    def test_huddle_message(self) -> None:
        hamlet = self.example_user("hamlet")
        sender = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        message_id = self.send_huddle_message(sender, [hamlet, cordelia])
        self.login("hamlet")

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id not in result.json()["user_ids"])
        self.assertTrue(sender.id not in result.json()["user_ids"])

        self.mark_message_read(hamlet, message_id)

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id in result.json()["user_ids"])
        self.assertTrue(sender.id not in result.json()["user_ids"])

    def test_inaccessible_stream_message(self) -> None:
        sender = self.example_user("othello")

        private_stream = "private stream"
        self.make_stream(stream_name=private_stream, invite_only=True)
        self.subscribe(sender, private_stream)

        message_id = self.send_stream_message(sender, private_stream, "read receipts")

        self.login("hamlet")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_error(result, "Invalid message(s)")

        self.login_user(sender)
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)

    def test_filter_deactivated_users(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        sender = self.example_user("othello")

        message_id = self.send_stream_message(sender, "Verona", "read receipts")

        # Mark message as read for hamlet and cordelia.
        self.mark_message_read(hamlet, message_id)
        self.mark_message_read(cordelia, message_id)

        # Login as cordelia and make sure hamlet is in read receipts before deactivation.
        self.login("cordelia")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id in result.json()["user_ids"])
        self.assertTrue(cordelia.id in result.json()["user_ids"])

        # Deactivate hamlet and verify hamlet is not in read receipts.
        do_deactivate_user(hamlet, acting_user=None)
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id not in result.json()["user_ids"])
        self.assertTrue(cordelia.id in result.json()["user_ids"])

        # Reactivate hamlet and verify hamlet appears again in read recipts.
        do_reactivate_user(hamlet, acting_user=None)
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertTrue(hamlet.id in result.json()["user_ids"])
        self.assertTrue(cordelia.id in result.json()["user_ids"])

    def test_send_read_receipts_privacy_setting(self) -> None:
        hamlet = self.example_user("hamlet")
        sender = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        message_id = self.send_stream_message(sender, "Verona", "read receipts")

        self.mark_message_read(hamlet, message_id)
        self.mark_message_read(cordelia, message_id)

        self.login("aaron")
        do_set_realm_property(sender.realm, "enable_read_receipts", False, acting_user=None)
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_error(result, "Read receipts are disabled in this organization.")

        do_set_realm_property(sender.realm, "enable_read_receipts", True, acting_user=None)
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertIn(hamlet.id, result.json()["user_ids"])
        self.assertIn(cordelia.id, result.json()["user_ids"])

        # Disable read receipts setting; confirm Cordelia no longer appears.
        do_change_user_setting(cordelia, "send_read_receipts", False, acting_user=cordelia)

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertIn(hamlet.id, result.json()["user_ids"])
        self.assertNotIn(cordelia.id, result.json()["user_ids"])

    def test_send_read_receipts_privacy_setting_bot(self) -> None:
        hamlet = self.example_user("hamlet")
        sender = self.example_user("othello")
        bot = self.example_user("default_bot")
        self.subscribe(bot, "Verona")

        message_id = self.send_stream_message(sender, "Verona", "read receipts")

        self.mark_message_read(hamlet, message_id)
        self.mark_message_read(bot, message_id)

        self.login("aaron")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertIn(hamlet.id, result.json()["user_ids"])
        self.assertIn(bot.id, result.json()["user_ids"])

        # Disable read receipts setting; confirm bot no longer appears.
        do_change_user_setting(bot, "send_read_receipts", False, acting_user=bot)

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertIn(hamlet.id, result.json()["user_ids"])
        self.assertNotIn(bot.id, result.json()["user_ids"])

    def test_historical_usermessages_read_flag_not_considered(self) -> None:
        """
        Ensure UserMessage rows with historical flag are also
        considered for read receipts.
        """
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        stream_name = "test stream"
        self.subscribe(cordelia, stream_name)

        message_id = self.send_stream_message(cordelia, stream_name, content="foo")

        self.login("hamlet")

        # Have hamlet react to the message to
        # create a historical UserMessage row.
        reaction_info = {
            "emoji_name": "smile",
        }
        result = self.client_post(f"/json/messages/{message_id}/reactions", reaction_info)
        self.assert_json_success(result)

        # Ensure UserMessage row with historical and read flags exists
        user_message = UserMessage.objects.get(user_profile=hamlet, message_id=message_id)
        self.assertTrue(user_message.flags.historical)
        self.assertTrue(user_message.flags.read)

        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        self.assert_json_success(result)
        self.assertIn(hamlet.id, result.json()["user_ids"])

    def test_filter_muted_users(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        # Hamlet mutes Cordelia
        add_user_mute(hamlet, cordelia, date_muted=timezone_now())
        # Cordelia mutes Othello
        add_user_mute(cordelia, othello, date_muted=timezone_now())

        # Iago sends a message
        message_id = self.send_stream_message(iago, "Verona", "read receipts")

        # Mark message as read for users.
        self.mark_message_read(hamlet, message_id)
        self.mark_message_read(cordelia, message_id)
        self.mark_message_read(othello, message_id)

        # Login as Iago and make sure all three users are in read receipts.
        self.login("iago")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["user_ids"], 3)
        self.assertTrue(hamlet.id in response_dict["user_ids"])
        self.assertTrue(cordelia.id in response_dict["user_ids"])
        self.assertTrue(othello.id in response_dict["user_ids"])

        # Login as Hamlet and make sure Cordelia is not in read receipts.
        self.login("hamlet")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["user_ids"], 2)
        self.assertTrue(hamlet.id in response_dict["user_ids"])
        self.assertFalse(cordelia.id in response_dict["user_ids"])
        self.assertTrue(othello.id in response_dict["user_ids"])

        # Login as Othello and make sure Cordelia is not in in read receipts.
        self.login("othello")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["user_ids"], 2)
        self.assertTrue(hamlet.id in response_dict["user_ids"])
        self.assertFalse(cordelia.id in response_dict["user_ids"])
        self.assertTrue(othello.id in response_dict["user_ids"])

        # Login as Cordelia and make sure Hamlet and Othello are not in read receipts.
        self.login("cordelia")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["user_ids"], 1)
        self.assertFalse(hamlet.id in response_dict["user_ids"])
        self.assertTrue(cordelia.id in response_dict["user_ids"])
        self.assertFalse(othello.id in response_dict["user_ids"])

        # Cordelia unmutes Othello
        mute_object = get_mute_object(cordelia, othello)
        assert mute_object is not None
        mute_object.delete()

        # Now Othello should appear in her read receipts, but not Hamlet.
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["user_ids"], 2)
        self.assertFalse(hamlet.id in response_dict["user_ids"])
        self.assertTrue(cordelia.id in response_dict["user_ids"])
        self.assertTrue(othello.id in response_dict["user_ids"])

        # Login as Othello and make sure all three users are in read receipts.
        self.login("othello")
        result = self.client_get(f"/json/messages/{message_id}/read_receipts")
        response_dict = self.assert_json_success(result)
        self.assert_length(response_dict["user_ids"], 3)
        self.assertTrue(hamlet.id in response_dict["user_ids"])
        self.assertTrue(cordelia.id in response_dict["user_ids"])
        self.assertTrue(othello.id in response_dict["user_ids"])
