from typing import Any, Dict, List, Mapping, Set

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_status import get_user_info_dict, update_user_status
from zerver.models import UserProfile, UserStatus, get_client


def get_away_user_ids(realm_id: int) -> Set[int]:
    user_dict = get_user_info_dict(realm_id)

    return {int(user_id) for user_id in user_dict if user_dict[user_id].get("away")}


def user_info(user: UserProfile) -> Dict[str, Any]:
    user_dict = get_user_info_dict(user.realm_id)
    return user_dict.get(str(user.id), {})


class UserStatusTest(ZulipTestCase):
    def test_basics(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        king_lear = self.lear_user("king")

        realm_id = hamlet.realm_id

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, set())

        client1 = get_client("web")
        client2 = get_client("ZT")

        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.AWAY,
            status_text=None,
            client_id=client1.id,
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {hamlet.id})

        # Test that second client just updates
        # the record.  We only store one record
        # per user.  The user's status transcends
        # clients; we only store the client for
        # reference and to maybe reconcile timeout
        # situations.
        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.AWAY,
            status_text="out to lunch",
            client_id=client2.id,
        )

        self.assertEqual(
            user_info(hamlet),
            dict(away=True, status_text="out to lunch"),
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {hamlet.id})

        rec_count = UserStatus.objects.filter(user_profile_id=hamlet.id).count()
        self.assertEqual(rec_count, 1)

        # Setting status_text to None causes it be ignored.
        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.NORMAL,
            status_text=None,
            client_id=client2.id,
        )

        self.assertEqual(
            user_info(hamlet),
            dict(status_text="out to lunch"),
        )

        # Clear the status_text now.
        update_user_status(
            user_profile_id=hamlet.id,
            status=None,
            status_text="",
            client_id=client2.id,
        )

        self.assertEqual(
            user_info(hamlet),
            {},
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, set())

        # Now set away status for three different users across
        # two realms.
        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.AWAY,
            status_text=None,
            client_id=client1.id,
        )
        update_user_status(
            user_profile_id=cordelia.id,
            status=UserStatus.AWAY,
            status_text=None,
            client_id=client2.id,
        )
        update_user_status(
            user_profile_id=king_lear.id,
            status=UserStatus.AWAY,
            status_text=None,
            client_id=client2.id,
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {cordelia.id, hamlet.id})

        away_user_ids = get_away_user_ids(realm_id=king_lear.realm.id)
        self.assertEqual(away_user_ids, {king_lear.id})

        # Set Hamlet to NORMAL but in a meeting.
        update_user_status(
            user_profile_id=hamlet.id,
            status=UserStatus.NORMAL,
            status_text="in a meeting",
            client_id=client2.id,
        )

        self.assertEqual(
            user_info(hamlet),
            dict(status_text="in a meeting"),
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {cordelia.id})

    def update_status_and_assert_event(
        self, payload: Dict[str, Any], expected_event: Dict[str, Any]
    ) -> None:
        events: List[Mapping[str, Any]] = []
        with self.tornado_redirected_to_list(events, expected_num_events=1):
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

        # Try a long message.
        long_text = "x" * 61
        payload = dict(status_text=long_text)
        result = self.client_post("/json/users/me/status", payload)
        self.assert_json_error(result, "status_text is too long (limit: 60 characters)")

        self.update_status_and_assert_event(
            payload=dict(
                away=orjson.dumps(True).decode(),
                status_text="on vacation",
            ),
            expected_event=dict(
                type="user_status", user_id=hamlet.id, away=True, status_text="on vacation"
            ),
        )
        self.assertEqual(
            user_info(hamlet),
            dict(away=True, status_text="on vacation"),
        )

        # Now revoke "away" status.
        self.update_status_and_assert_event(
            payload=dict(away=orjson.dumps(False).decode()),
            expected_event=dict(type="user_status", user_id=hamlet.id, away=False),
        )
        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, set())

        # And now just update your info.
        # The server will trim the whitespace here.
        self.update_status_and_assert_event(
            payload=dict(status_text="   in office  "),
            expected_event=dict(type="user_status", user_id=hamlet.id, status_text="in office"),
        )

        self.assertEqual(
            user_info(hamlet),
            dict(status_text="in office"),
        )

        # And finally clear your info.
        self.update_status_and_assert_event(
            payload=dict(status_text=""),
            expected_event=dict(type="user_status", user_id=hamlet.id, status_text=""),
        )
        self.assertEqual(
            get_user_info_dict(realm_id=realm_id),
            {},
        )

        # Turn on "away" status again.
        self.update_status_and_assert_event(
            payload=dict(away=orjson.dumps(True).decode()),
            expected_event=dict(type="user_status", user_id=hamlet.id, away=True),
        )
        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {hamlet.id})

        # And set status text while away.
        self.update_status_and_assert_event(
            payload=dict(status_text="   at the beach  "),
            expected_event=dict(type="user_status", user_id=hamlet.id, status_text="at the beach"),
        )
        self.assertEqual(
            user_info(hamlet),
            dict(status_text="at the beach", away=True),
        )

        away_user_ids = get_away_user_ids(realm_id=realm_id)
        self.assertEqual(away_user_ids, {hamlet.id})
