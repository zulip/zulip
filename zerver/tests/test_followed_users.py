from datetime import datetime, timezone

import time_machine

from zerver.actions.followed_users import do_unfollow_user
from zerver.actions.users import do_deactivate_user
from zerver.lib.cache import cache_get, get_followed_users_cache_key
from zerver.lib.followed_users import get_follow_object, get_following_users, get_user_follows
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import FollowedUser


class FollowedUsersTests(ZulipTestCase):
    # Hamlet does the following/unfollowing, and Cordelia gets followed/unfollowed.

    def test_get_user_follows(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        followed_users = get_user_follows(hamlet)
        self.assertEqual(followed_users, [])
        follow_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        with time_machine.travel(follow_time, tick=False):
            url = f"/api/v1/users/me/followed_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        followed_users = get_user_follows(hamlet)
        self.assert_length(followed_users, 1)

        self.assertDictEqual(
            followed_users[0],
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(follow_time),
            },
        )

    def test_follow_self(self) -> None:
        hamlet = self.example_user("hamlet")

        url = f"/api/v1/users/me/followed_users/{hamlet.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "You cannot follow yourself.")

    def test_follow_bot(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        bot_info = {
            "full_name": "The Bot of Hamlet",
            "short_name": "hambot",
            "bot_type": "1",
        }
        result = self.client_post("/json/bots", bot_info)
        followed_id = self.assert_json_success(result)["user_id"]

        url = f"/api/v1/users/me/followed_users/{followed_id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        url = f"/api/v1/users/me/followed_users/{followed_id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)

    def test_follow_already_followed(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "User is already followed.")

    def _test_follow_valid_data(self, deactivate_user: bool = False) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        follow_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        if deactivate_user:
            do_deactivate_user(cordelia, acting_user=None)

        with time_machine.travel(follow_time, tick=False):
            url = f"/api/v1/users/me/followed_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        self.assertIn(
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(follow_time),
            },
            get_user_follows(hamlet),
        )
        self.assertIsNotNone(get_follow_object(hamlet, cordelia))

    def test_follow_valid_data(self) -> None:
        self._test_follow_valid_data()

    def test_follow_deactivated_user(self) -> None:
        self._test_follow_valid_data(deactivate_user=True)

    def test_unfollow_before_following(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_error(result, "User is not followed.")

    def _test_unfollow_valid_data(self, deactivate_user: bool = False) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        follow_time = datetime(2021, 1, 1, tzinfo=timezone.utc)

        if deactivate_user:
            do_deactivate_user(cordelia, acting_user=None)

        with time_machine.travel(follow_time, tick=False):
            url = f"/api/v1/users/me/followed_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)

        self.assertNotIn(
            {
                "id": cordelia.id,
                "timestamp": datetime_to_timestamp(follow_time),
            },
            get_user_follows(hamlet),
        )
        self.assertIsNone(get_follow_object(hamlet, cordelia))
        self.assertEqual(
            FollowedUser.objects.filter(
                user_profile=hamlet, followed_user=cordelia
            ).count(),
            0,
        )

    def test_unfollow_valid_data(self) -> None:
        self._test_unfollow_valid_data()

    def test_unfollow_deactivated_user(self) -> None:
        self._test_unfollow_valid_data(deactivate_user=True)

    def test_get_following_users_cache(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        self.assertEqual(None, cache_get(get_followed_users_cache_key(cordelia.id)))
        self.assertEqual(set(), get_following_users(cordelia.id))
        self.assertEqual(set(), cache_get(get_followed_users_cache_key(cordelia.id))[0])

        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)
        self.assertEqual(None, cache_get(get_followed_users_cache_key(cordelia.id)))
        self.assertEqual({hamlet.id}, get_following_users(cordelia.id))
        self.assertEqual(
            {hamlet.id}, cache_get(get_followed_users_cache_key(cordelia.id))[0]
        )

        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)
        self.assertEqual(None, cache_get(get_followed_users_cache_key(cordelia.id)))
        self.assertEqual(set(), get_following_users(cordelia.id))
        self.assertEqual(set(), cache_get(get_followed_users_cache_key(cordelia.id))[0])

    def test_follow_sends_event(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        with self.capture_send_event_calls(expected_num_events=1) as events:
            url = f"/api/v1/users/me/followed_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        event = events[0]["event"]
        self.assertEqual(event["type"], "followed_users")
        self.assertEqual(events[0]["users"], [hamlet.id])
        followed_ids = [entry["id"] for entry in event["followed_users"]]
        self.assertIn(cordelia.id, followed_ids)

    def test_unfollow_sends_event(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        with self.capture_send_event_calls(expected_num_events=1) as events:
            url = f"/api/v1/users/me/followed_users/{cordelia.id}"
            result = self.api_delete(hamlet, url)
            self.assert_json_success(result)

        event = events[0]["event"]
        self.assertEqual(event["type"], "followed_users")
        self.assertEqual(events[0]["users"], [hamlet.id])
        self.assertEqual(event["followed_users"], [])

    def test_unfollow_is_idempotent_at_action_layer(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Call do_unfollow_user without a prior follow — it should not raise,
        # and should still emit an event.
        with self.capture_send_event_calls(expected_num_events=1) as events:
            do_unfollow_user(hamlet, cordelia)

        event = events[0]["event"]
        self.assertEqual(event["type"], "followed_users")
        self.assertIsNone(get_follow_object(hamlet, cordelia))
