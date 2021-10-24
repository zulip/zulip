from datetime import datetime, timezone
from unittest import mock

import orjson

from zerver.lib.actions import do_deactivate_user
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
            url = f"/api/v1/users/me/muted_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        muted_users = get_user_mutes(hamlet)
        self.assert_length(muted_users, 1)

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

        url = f"/api/v1/users/me/muted_users/{hamlet.id}"
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

        url = f"/api/v1/users/me/muted_users/{muted_id}"
        result = self.api_post(hamlet, url)
        # Currently we do not allow muting bots. This is the error message
        # from `access_user_by_id`.
        self.assert_json_error(result, "No such user")

    def test_add_muted_user_mute_twice(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "User already muted")

    def _test_add_muted_user_valid_data(self, deactivate_user: bool = False) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        if deactivate_user:
            do_deactivate_user(cordelia, acting_user=None)

        with mock.patch("zerver.views.muting.timezone_now", return_value=mute_time):
            url = f"/api/v1/users/me/muted_users/{cordelia.id}"
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
        self.assert_length(audit_log_entries, 1)
        audit_log_entry = audit_log_entries[0]
        self.assertEqual(
            audit_log_entry,
            (
                RealmAuditLog.USER_MUTED,
                mute_time,
                orjson.dumps({"muted_user_id": cordelia.id}).decode(),
            ),
        )

    def test_add_muted_user_valid_data(self) -> None:
        self._test_add_muted_user_valid_data()

    def test_add_muted_user_deactivated_user(self) -> None:
        self._test_add_muted_user_valid_data(deactivate_user=True)

    def test_remove_muted_user_unmute_before_muting(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_error(result, "User is not muted")

    def _test_remove_muted_user_valid_data(self, deactivate_user: bool = False) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        mute_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        if deactivate_user:
            do_deactivate_user(cordelia, acting_user=None)

        with mock.patch("zerver.views.muting.timezone_now", return_value=mute_time):
            url = f"/api/v1/users/me/muted_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        with mock.patch("zerver.lib.actions.timezone_now", return_value=mute_time):
            # To test that `RealmAuditLog` entry has correct `event_time`.
            url = f"/api/v1/users/me/muted_users/{cordelia.id}"
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
        self.assert_length(audit_log_entries, 2)
        audit_log_entry = audit_log_entries[1]
        self.assertEqual(
            audit_log_entry,
            (
                RealmAuditLog.USER_UNMUTED,
                mute_time,
                orjson.dumps({"unmuted_user_id": cordelia.id}).decode(),
            ),
        )

    def test_remove_muted_user_valid_data(self) -> None:
        self._test_remove_muted_user_valid_data()

    def test_remove_muted_user_deactivated_user(self) -> None:
        self._test_remove_muted_user_valid_data(deactivate_user=True)

    def test_get_muting_users(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        self.assertEqual(None, cache_get(get_muting_users_cache_key(cordelia.id)))
        self.assertEqual(set(), get_muting_users(cordelia.id))
        self.assertEqual(set(), cache_get(get_muting_users_cache_key(cordelia.id))[0])

        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)
        self.assertEqual(None, cache_get(get_muting_users_cache_key(cordelia.id)))
        self.assertEqual({hamlet.id}, get_muting_users(cordelia.id))
        self.assertEqual({hamlet.id}, cache_get(get_muting_users_cache_key(cordelia.id))[0])

        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)
        self.assertEqual(None, cache_get(get_muting_users_cache_key(cordelia.id)))
        self.assertEqual(set(), get_muting_users(cordelia.id))
        self.assertEqual(set(), cache_get(get_muting_users_cache_key(cordelia.id))[0])

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
        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
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
        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
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

    def test_muted_message_send_notifications_not_enqueued(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")

        # No muting involved. Notification about to be enqueued for Hamlet.
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as m:
            self.send_personal_message(cordelia, hamlet)
            m.assert_called_once()

        # Hamlet mutes Cordelia.
        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        # Cordelia has been muted. Notification will not be enqueued for Hamlet.
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as m:
            self.send_personal_message(cordelia, hamlet)
            m.assert_not_called()

    def test_muted_message_edit_notifications_not_enqueued(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        cordelia = self.example_user("cordelia")
        self.make_stream("general")
        self.subscribe(hamlet, "general")

        # No muting. Only Hamlet is subscribed to #general, so only he can potentially receive
        # notifications.
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as m:
            message_id = self.send_stream_message(cordelia, "general")
            # Message does not mention Hamlet, so no notification.
            m.assert_not_called()

        self.login("cordelia")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as m:
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                dict(
                    message_id=message_id,
                    content="@**King Hamlet**",
                ),
            )
            self.assert_json_success(result)
            m.assert_called_once()
            # `maybe_enqueue_notificaions` was called for Hamlet after message edit mentioned him.
            self.assertEqual(m.call_args_list[0][1]["user_notifications_data"].user_id, hamlet.id)

        # Hamlet mutes Cordelia.
        self.login("hamlet")
        url = f"/api/v1/users/me/muted_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as m:
            message_id = self.send_stream_message(cordelia, "general")
            m.assert_not_called()

        self.login("cordelia")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as m:
            result = self.client_patch(
                "/json/messages/" + str(message_id),
                dict(
                    message_id=message_id,
                    content="@**King Hamlet**",
                ),
            )
            self.assert_json_success(result)
            # `maybe_enqueue_notificaions` wasn't called for Hamlet after message edit which mentioned him,
            # because the sender (Cordelia) was muted.
            m.assert_not_called()
