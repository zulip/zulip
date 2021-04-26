from datetime import datetime, timezone
from unittest import mock

import orjson

from zerver.lib.cache import cache_get, get_muting_users_cache_key
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_mutes import get_mute_object, get_muting_users, get_user_mutes
from zerver.models import RealmAuditLog, UserMessage, UserProfile


class MutedUsersTests(ZulipTestCase):
    # Hamlet does the muting/unmuting, and Cordelia gets muted/unmuted.
    def test_get_user_mutes(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        muted_users = get_user_mutes(hamlet)
        self.assertEqual(muted_users, [])
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        with mock.patch("zerver.views.muting.timezone_now", return_value=mute_time):
            url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        muted_users = get_user_mutes(hamlet)
        self.assertEqual(len(muted_users), 1)

        self.assertDictEqual(
            muted_users[0],
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(mute_time),
            },
        )

    def test_add_muted_user_mute_self(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        url = "/api/v1/users/me/muted_users/{}".format(hamlet.id)
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "Cannot mute self")

    def test_add_muted_user_mute_bot(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        bot_info = {
            "full_name": "The Bot of Hamlet",
            "short_name": "hambot",
            "bot_type": "1",
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        muted_id = result.json()["user_id"]

        url = "/api/v1/users/me/muted_users/{}".format(muted_id)
        result = self.api_post(hamlet, url)
        # Currently we do not allow muting bots. This is the error message
        # from `access_user_by_id`.
        self.assert_json_error(result, "No such user")

    def test_add_muted_user_mute_twice(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "User already muted")

    def test_add_muted_user_valid_data(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        with mock.patch("zerver.views.muting.timezone_now", return_value=mute_time):
            url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        self.assertIn(
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(mute_time),
            },
            get_user_mutes(hamlet),
        )
        self.assertIsNotNone(get_mute_object(hamlet, cordelia))

        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=hamlet, modified_user=hamlet).values_list(
                "event_type", "event_time", "extra_data"
            )
        )
        self.assertEqual(len(audit_log_entries), 1)
        audit_log_entry = audit_log_entries[0]
        self.assertEqual(
            audit_log_entry,
            (
                RealmAuditLog.USER_MUTED,
                mute_time,
                orjson.dumps({"muted_user_id": cordelia.id}).decode(),
            ),
        )

    def test_remove_muted_user_unmute_before_muting(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_delete(hamlet, url)
        self.assert_json_error(result, "User is not muted")

    def test_remove_muted_user_valid_data(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        with mock.patch("zerver.views.muting.timezone_now", return_value=mute_time):
            url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        with mock.patch("zerver.lib.actions.timezone_now", return_value=mute_time):
            # To test that `RealmAuditLog` entry has correct `event_time`.
            url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
            result = self.api_delete(hamlet, url)

        self.assert_json_success(result)
        self.assertNotIn(
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(mute_time),
            },
            get_user_mutes(hamlet),
        )
        self.assertIsNone(get_mute_object(hamlet, cordelia))

        audit_log_entries = list(
            RealmAuditLog.objects.filter(acting_user=hamlet, modified_user=hamlet)
            .values_list("event_type", "event_time", "extra_data")
            .order_by("id")
        )
        self.assertEqual(len(audit_log_entries), 2)
        audit_log_entry = audit_log_entries[1]
        self.assertEqual(
            audit_log_entry,
            (
                RealmAuditLog.USER_UNMUTED,
                mute_time,
                orjson.dumps({"unmuted_user_id": cordelia.id}).decode(),
            ),
        )

    def test_get_muting_users(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        self.assertEqual(None, cache_get(get_muting_users_cache_key(cordelia)))
        self.assertEqual(set(), get_muting_users(cordelia))
        self.assertEqual(set(), cache_get(get_muting_users_cache_key(cordelia))[0])

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)
        self.assertEqual(None, cache_get(get_muting_users_cache_key(cordelia)))
        self.assertEqual({hamlet.id}, get_muting_users(cordelia))
        self.assertEqual({hamlet.id}, cache_get(get_muting_users_cache_key(cordelia))[0])

        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)
        self.assertEqual(None, cache_get(get_muting_users_cache_key(cordelia)))
        self.assertEqual(set(), get_muting_users(cordelia))
        self.assertEqual(set(), cache_get(get_muting_users_cache_key(cordelia))[0])

    def assert_usermessage_read_flag(self, user: UserProfile, message: int, flag: bool) -> None:
        usermesaage = UserMessage.objects.get(
            user_profile=user,
            message=message,
        )
        self.assertTrue(usermesaage.flags.read == flag)

    def test_new_messages_from_muted_user_marked_as_read(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        self.make_stream("general")
        self.subscribe(hamlet, "general")
        self.subscribe(cordelia, "general")
        self.subscribe(othello, "general")

        # Hamlet mutes Cordelia.
        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        # Have Cordelia send messages to Hamlet and Othello.
        stream_message = self.send_stream_message(cordelia, "general", "Spam in stream")
        huddle_message = self.send_huddle_message(cordelia, [hamlet, othello], "Spam in huddle")
        pm_to_hamlet = self.send_personal_message(cordelia, hamlet, "Spam in PM")
        pm_to_othello = self.send_personal_message(cordelia, othello, "Spam in PM")

        # These should be marked as read for Hamlet, since he has muted Cordelia.
        self.assert_usermessage_read_flag(hamlet, stream_message, True)
        self.assert_usermessage_read_flag(hamlet, huddle_message, True)
        self.assert_usermessage_read_flag(hamlet, pm_to_hamlet, True)

        # These messages should be unreads for Othello, since he hasn't muted Cordelia.
        self.assert_usermessage_read_flag(othello, stream_message, False)
        self.assert_usermessage_read_flag(othello, huddle_message, False)
        self.assert_usermessage_read_flag(othello, pm_to_othello, False)

    def test_existing_messages_from_muted_user_marked_as_read(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        self.make_stream("general")
        self.subscribe(hamlet, "general")
        self.subscribe(cordelia, "general")
        self.subscribe(othello, "general")

        # Have Cordelia send messages to Hamlet and Othello.
        stream_message = self.send_stream_message(cordelia, "general", "Spam in stream")
        huddle_message = self.send_huddle_message(cordelia, [hamlet, othello], "Spam in huddle")
        pm_to_hamlet = self.send_personal_message(cordelia, hamlet, "Spam in PM")
        pm_to_othello = self.send_personal_message(cordelia, othello, "Spam in PM")

        # These messages are unreads for both Hamlet and Othello right now.
        self.assert_usermessage_read_flag(hamlet, stream_message, False)
        self.assert_usermessage_read_flag(hamlet, huddle_message, False)
        self.assert_usermessage_read_flag(hamlet, pm_to_hamlet, False)

        self.assert_usermessage_read_flag(othello, stream_message, False)
        self.assert_usermessage_read_flag(othello, huddle_message, False)
        self.assert_usermessage_read_flag(othello, pm_to_othello, False)

        # Hamlet mutes Cordelia.
        url = "/api/v1/users/me/muted_users/{}".format(cordelia.id)
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        # The messages sent earlier should be marked as read for Hamlet.
        self.assert_usermessage_read_flag(hamlet, stream_message, True)
        self.assert_usermessage_read_flag(hamlet, huddle_message, True)
        self.assert_usermessage_read_flag(hamlet, pm_to_hamlet, True)

        # These messages are still unreads for Othello, since he did not mute Cordelia.
        self.assert_usermessage_read_flag(othello, stream_message, False)
        self.assert_usermessage_read_flag(othello, huddle_message, False)
        self.assert_usermessage_read_flag(othello, pm_to_othello, False)
