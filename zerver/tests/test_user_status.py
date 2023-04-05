from typing import Any, Dict

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_status import UserInfoDict, get_user_status_dict, update_user_status
from zerver.models import UserProfile, UserStatus, get_client


def user_status_info(user: UserProfile) -> UserInfoDict:
    user_dict = get_user_status_dict(user.realm_id)
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

        # Clear the status_text and emoji_info now.
        update_user_status(
            user_profile_id=hamlet.id,
            status_text="",
            emoji_name="",
            emoji_code="",
            reaction_type=UserStatus.UNICODE_EMOJI,
            client_id=client2.id,
        )

        self.assertEqual(
            user_status_info(hamlet),
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
        )

        self.assertEqual(
            user_status_info(hamlet),
            dict(status_text="in a meeting"),
        )

    def update_status_and_assert_event(
        self, payload: Dict[str, Any], expected_event: Dict[str, Any], num_events: int = 1
    ) -> None:
        with self.capture_send_event_calls(expected_num_events=num_events) as events:
            result = self.client_post("/json/users/me/status", payload)
        self.assert_json_success(result)
        self.assertEqual(events[0]["event"], expected_event)

    def test_endpoints(self) -> None:
        hamlet = self.example_user("hamlet")
        realm_id = hamlet.realm_id

        self.login_user(hamlet)

        # Try to omit parameter--this should be an error.
        payload: Dict[str, Any] = {}
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

        # And finally clear your info.
        self.update_status_and_assert_event(
            payload=dict(status_text=""),
            expected_event=dict(type="user_status", user_id=hamlet.id, status_text=""),
        )
        self.assertEqual(
            get_user_status_dict(realm_id=realm_id),
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
