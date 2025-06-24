from typing import Any

import orjson
import time_machine
from django.utils.timezone import now as timezone_now

from zerver.actions.user_status import try_clear_scheduled_user_status
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_status import (
    UserInfoDict,
    get_all_users_status_dict,
    get_user_status,
    update_user_status,
)
from zerver.models import UserProfile, UserStatus
from zerver.models.clients import get_client
from zerver.models.presence import UserPresence


def user_status_info(user: UserProfile, acting_user: UserProfile | None = None) -> UserInfoDict:
    if acting_user is None:
        acting_user = user
    user_dict = get_all_users_status_dict(user.realm, acting_user)
    return user_dict.get(str(user.id), {})


class UserStatusTest(ZulipTestCase):
    def test_basics(self) -> None:
        hamlet = self.example_user("hamlet")

        client1 = get_client("web")
        client2 = get_client("ZT")

        update_user_status(
            user_profile_id=hamlet.id,
            status_text="working",
            emoji_name=None,
            emoji_code=None,
            reaction_type=None,
            client_id=client1.id,
            scheduled_end_time=None,
        )

        self.assertEqual(
            user_status_info(hamlet),
            dict(
                status_text="working",
            ),
        )

        rec_count = UserStatus.objects.filter(user_profile_id=hamlet.id).count()
        self.assertEqual(rec_count, 1)

        # Test that second client just updates
        # the record.  We only store one record
        # per user.  The user's status transcends
        # clients; we only store the client for
        # reference and to maybe reconcile timeout
        # situations.
        update_user_status(
            user_profile_id=hamlet.id,
            status_text="out to lunch",
            emoji_name="car",
            emoji_code="1f697",
            reaction_type=UserStatus.UNICODE_EMOJI,
            client_id=client2.id,
            scheduled_end_time=None,
        )
        self.assertEqual(
            user_status_info(hamlet),
            dict(
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )

        fetched_status = get_user_status(hamlet)
        self.assertEqual(
            fetched_status,
            dict(
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )

        rec_count = UserStatus.objects.filter(user_profile_id=hamlet.id).count()
        self.assertEqual(rec_count, 1)

        # Setting status_text and emoji_info to None causes it be ignored.
        update_user_status(
            user_profile_id=hamlet.id,
            status_text=None,
            emoji_name=None,
            emoji_code=None,
            reaction_type=None,
            client_id=client2.id,
            scheduled_end_time=None,
        )

        self.assertEqual(
            user_status_info(hamlet),
            dict(
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )

        fetched_status = get_user_status(hamlet)
        self.assertEqual(
            fetched_status,
            dict(
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )

        # Clear the status_text and emoji_info now.
        update_user_status(
            user_profile_id=hamlet.id,
            status_text="",
            emoji_name="",
            emoji_code="",
            reaction_type=UserStatus.UNICODE_EMOJI,
            client_id=client2.id,
            scheduled_end_time=None,
        )

        self.assertEqual(
            user_status_info(hamlet),
            {},
        )

        fetched_status = get_user_status(hamlet)
        self.assertEqual(
            fetched_status,
            {},
        )

        # Set Hamlet to in a meeting.
        update_user_status(
            user_profile_id=hamlet.id,
            status_text="in a meeting",
            emoji_name=None,
            emoji_code=None,
            reaction_type=None,
            client_id=client2.id,
            scheduled_end_time=None,
        )

        self.assertEqual(
            user_status_info(hamlet),
            dict(status_text="in a meeting"),
        )

        fetched_status = get_user_status(hamlet)
        self.assertEqual(
            fetched_status,
            dict(status_text="in a meeting"),
        )

        # Test user status for inaccessible users.
        self.set_up_db_for_testing_user_access()
        cordelia = self.example_user("cordelia")
        update_user_status(
            user_profile_id=cordelia.id,
            status_text="on vacation",
            emoji_name=None,
            emoji_code=None,
            reaction_type=None,
            client_id=client2.id,
            scheduled_end_time=None,
        )
        self.assertEqual(
            user_status_info(hamlet, self.example_user("polonius")),
            dict(status_text="in a meeting"),
        )
        self.assertEqual(
            user_status_info(cordelia, self.example_user("polonius")),
            {},
        )

    def update_status_and_assert_event(
        self, payload: dict[str, Any], expected_event: dict[str, Any], num_events: int = 1
    ) -> None:
        with self.capture_send_event_calls(expected_num_events=num_events) as events:
            result = self.client_post("/json/users/me/status", payload)
        self.assert_json_success(result)
        if num_events == 1:
            self.assertEqual(events[0]["event"], expected_event)
        else:
            self.assertEqual(events[2]["event"], expected_event)

    def test_clear_statuses_upon_expiry(self) -> None:
        hamlet = self.example_user("hamlet")

        self.login_user(hamlet)
        client1 = get_client("web")
        scheduled_timestamp = datetime_to_timestamp(timezone_now()) + 100000
        scheduled_timestamp_expired = scheduled_timestamp - 100000

        # Set a user status with some end time.
        update_user_status(
            user_profile_id=hamlet.id,
            status_text="out to lunch",
            emoji_name="car",
            emoji_code="1f697",
            reaction_type=UserStatus.UNICODE_EMOJI,
            client_id=client1.id,
            scheduled_end_time=scheduled_timestamp_expired,
        )
        rec_count = UserStatus.objects.filter(user_profile_id=hamlet.id).count()
        self.assertEqual(rec_count, 1)

        # When time not yet reached, status not cleared
        with time_machine.travel(scheduled_timestamp_expired - 5 * 60, tick=False):
            clear_status = try_clear_scheduled_user_status()

        self.assertEqual(clear_status, False)
        self.assertEqual(
            user_status_info(hamlet),
            dict(
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
                scheduled_end_time=scheduled_timestamp_expired,
            ),
        )

        # Clear all statuses which have crossed their expiry time
        with time_machine.travel(scheduled_timestamp, tick=False):
            clear_status = try_clear_scheduled_user_status()

        self.assertEqual(clear_status, True)
        self.assertEqual(user_status_info(hamlet), {})

        # Test scheduling time to clear status, with no status set
        payload: dict[str, Any] = {"scheduled_end_time": scheduled_timestamp}
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(result, "Client does not have any status set.")

        # Test setting status with already expired status expiry time
        payload = {"status_text": "In a meeting", "scheduled_end_time": scheduled_timestamp_expired}
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_success(result)
        self.assertEqual(user_status_info(hamlet), dict())

    def test_endpoints(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm
        now = timezone_now()

        self.login_user(hamlet)

        # Set up an initial presence state for the user.
        UserPresence.objects.filter(user_profile=hamlet).delete()
        with time_machine.travel(now, tick=False):
            result = self.api_post(
                hamlet,
                "/api/v1/users/me/presence",
                dict(status="active"),
                HTTP_USER_AGENT="ZulipAndroid/1.0",
            )
            self.assert_json_success(result)

        # Try to omit parameter--this should be an error.
        payload: dict[str, Any] = {}
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(result, "Client did not pass any new values.")

        # Try to omit emoji_name parameter but passing emoji_code --this should be an error.
        payload = {"status_text": "In a meeting", "emoji_code": "1f4bb"}
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(
            result, "Client must pass emoji_name if they pass either emoji_code or reaction_type."
        )

        # Invalid emoji requests fail.
        payload = {"status_text": "In a meeting", "emoji_code": "1f4bb", "emoji_name": "invalid"}
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(result, "Emoji 'invalid' does not exist")

        payload = {"status_text": "In a meeting", "emoji_code": "1f4bb", "emoji_name": "car"}
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(result, "Invalid emoji name.")

        payload = {
            "status_text": "In a meeting",
            "emoji_code": "1f4bb",
            "emoji_name": "car",
            "reaction_type": "realm_emoji",
        }
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(result, "Invalid custom emoji.")

        # Try a long message--this should be an error.
        long_text = "x" * 61
        payload = dict(status_text=long_text)
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(result, "status_text is too long (limit: 60 characters)")

        # Set "away" with a normal length message.
        self.update_status_and_assert_event(
            payload=dict(
                away=orjson.dumps(True).decode(),
                status_text="on vacation",
            ),
            expected_event=dict(
                type="user_status", user_id=hamlet.id, away=True, status_text="on vacation"
            ),
            num_events=4,
        )
        self.assertEqual(
            user_status_info(hamlet),
            dict(away=True, status_text="on vacation"),
        )

        result = self.client_get(f"/json/users/{hamlet.id}/status")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            result_dict["status"],
            dict(away=True, status_text="on vacation"),
        )

        # Setting away is a deprecated way of accessing a user's presence_enabled
        # setting. Can be removed when clients migrate "away" (also referred to as
        # "unavailable") feature to directly use the presence_enabled setting.
        user = UserProfile.objects.get(id=hamlet.id)
        self.assertEqual(user.presence_enabled, False)

        # Server should fill emoji_code and reaction_type by emoji_name.
        self.update_status_and_assert_event(
            payload=dict(
                emoji_name="car",
            ),
            expected_event=dict(
                type="user_status",
                user_id=hamlet.id,
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )
        self.assertEqual(
            user_status_info(hamlet),
            dict(
                away=True,
                status_text="on vacation",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )

        result = self.client_get(f"/json/users/{hamlet.id}/status")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            result_dict["status"],
            dict(
                away=True,
                status_text="on vacation",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )

        # Server should remove emoji_code and reaction_type if emoji_name is empty.
        self.update_status_and_assert_event(
            payload=dict(
                emoji_name="",
            ),
            expected_event=dict(
                type="user_status",
                user_id=hamlet.id,
                emoji_name="",
                emoji_code="",
                reaction_type=UserStatus.UNICODE_EMOJI,
            ),
        )
        self.assertEqual(
            user_status_info(hamlet),
            dict(away=True, status_text="on vacation"),
        )

        result = self.client_get(f"/json/users/{hamlet.id}/status")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            result_dict["status"],
            dict(away=True, status_text="on vacation"),
        )

        # Now revoke "away" status.
        self.update_status_and_assert_event(
            payload=dict(away=orjson.dumps(False).decode()),
            expected_event=dict(type="user_status", user_id=hamlet.id, away=False),
            num_events=4,
        )
        self.assertEqual(
            user_status_info(hamlet),
            dict(status_text="on vacation"),
        )

        # Setting away is a deprecated way of accessing a user's presence_enabled
        # setting. Can be removed when clients migrate "away" (also referred to as
        # "unavailable") feature to directly use the presence_enabled setting.
        user = UserProfile.objects.get(id=hamlet.id)
        self.assertEqual(user.presence_enabled, True)

        # And now just update your info.
        # The server will trim the whitespace here.
        self.update_status_and_assert_event(
            payload=dict(status_text="   in office  "),
            expected_event=dict(type="user_status", user_id=hamlet.id, status_text="in office"),
        )
        self.assertEqual(
            user_status_info(hamlet),
            dict(status_text="in office"),
        )

        result = self.client_get(f"/json/users/{hamlet.id}/status")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            result_dict["status"],
            dict(status_text="in office"),
        )

        # And finally clear your info.
        self.update_status_and_assert_event(
            payload=dict(status_text=""),
            expected_event=dict(type="user_status", user_id=hamlet.id, status_text=""),
        )
        self.assertEqual(
            get_all_users_status_dict(realm=realm, user_profile=hamlet),
            {},
        )

        result = self.client_get(f"/json/users/{hamlet.id}/status")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            result_dict["status"],
            {},
        )

        # Turn on "away" status again.
        self.update_status_and_assert_event(
            payload=dict(away=orjson.dumps(True).decode()),
            expected_event=dict(type="user_status", user_id=hamlet.id, away=True),
            num_events=4,
        )

        # Setting away is a deprecated way of accessing a user's presence_enabled
        # setting. Can be removed when clients migrate "away" (also referred to as
        # "unavailable") feature to directly use the presence_enabled setting.
        user = UserProfile.objects.get(id=hamlet.id)
        self.assertEqual(user.presence_enabled, False)

        # And set status text while away.
        self.update_status_and_assert_event(
            payload=dict(status_text="   at the beach  "),
            expected_event=dict(type="user_status", user_id=hamlet.id, status_text="at the beach"),
        )
        self.assertEqual(
            user_status_info(hamlet),
            dict(status_text="at the beach", away=True),
        )

        result = self.client_get(f"/json/users/{hamlet.id}/status")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            result_dict["status"],
            dict(status_text="at the beach", away=True),
        )

        # Invalid user ID should fail
        result = self.client_get("/json/users/12345/status")
        self.assert_json_error(result, "No such user")

        # Test status if the status has not been set
        iago = self.example_user("iago")
        result = self.client_get(f"/json/users/{iago.id}/status")
        result_dict = self.assert_json_success(result)
        self.assertEqual(
            result_dict["status"],
            {},
        )
