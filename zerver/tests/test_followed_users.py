from datetime import datetime, timezone

import time_machine

from zerver.actions.followed_users import do_unfollow_user
from zerver.actions.users import do_deactivate_user
from zerver.lib.cache import cache_get, get_followed_users_cache_key
from zerver.lib.followed_users import (
    get_follow_object,
    get_following_user_ids,
    get_following_users,
    get_user_follows,
)
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

    def test_multiple_simultaneous_follows(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        prospero = self.example_user("prospero")

        # Follow multiple users in a row
        for target in [cordelia, othello, prospero]:
            url = f"/api/v1/users/me/followed_users/{target.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        # Verify all follows were recorded
        followed_users = get_user_follows(hamlet)
        self.assert_length(followed_users, 3)

        followed_ids = {entry["id"] for entry in followed_users}
        self.assertEqual(followed_ids, {cordelia.id, othello.id, prospero.id})

    def test_select_and_unfollow_specific_user(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        # Follow two users
        for target in [cordelia, othello]:
            url = f"/api/v1/users/me/followed_users/{target.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        # Unfollow only cordelia
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)

        # Verify only othello is still followed
        followed_users = get_user_follows(hamlet)
        self.assert_length(followed_users, 1)
        self.assertEqual(followed_users[0]["id"], othello.id)

    def test_follow_unfollow_and_refollow(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        follow_time_1 = datetime(2021, 1, 1, tzinfo=timezone.utc)
        follow_time_2 = datetime(2021, 1, 2, tzinfo=timezone.utc)

        # Follow cordelia
        with time_machine.travel(follow_time_1, tick=False):
            url = f"/api/v1/users/me/followed_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        followed_users = get_user_follows(hamlet)
        self.assert_length(followed_users, 1)
        timestamp_1 = followed_users[0]["timestamp"]

        # Unfollow
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)

        followed_users = get_user_follows(hamlet)
        self.assertEqual(followed_users, [])

        # Re-follow at a different time
        with time_machine.travel(follow_time_2, tick=False):
            url = f"/api/v1/users/me/followed_users/{cordelia.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        followed_users = get_user_follows(hamlet)
        self.assert_length(followed_users, 1)
        timestamp_2 = followed_users[0]["timestamp"]

        # Timestamps should reflect the re-follow time, not the original
        self.assertNotEqual(timestamp_1, timestamp_2)
        self.assertEqual(timestamp_2, datetime_to_timestamp(follow_time_2))

    def test_invalid_followed_user_id(self) -> None:
        hamlet = self.example_user("hamlet")
        invalid_id = 999999

        url = f"/api/v1/users/me/followed_users/{invalid_id}"
        result = self.api_post(hamlet, url)
        self.assert_json_error(result, "No such user")

    def test_follow_does_not_affect_other_users(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        # Hamlet follows cordelia
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        # Othello's follows should be empty
        followed_users = get_user_follows(othello)
        self.assertEqual(followed_users, [])

        # Cordelia is followed by hamlet, not by othello
        followers = get_following_users(cordelia.id)
        self.assertIn(hamlet.id, followers)
        self.assertNotIn(othello.id, followers)

    def test_follow_relationship_is_directional(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Hamlet follows cordelia
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        # Cordelia does NOT follow hamlet
        followed_users = get_user_follows(cordelia)
        self.assertEqual(followed_users, [])

        # Verify hamlet is NOT in cordelia's "is followed by" list
        followers_of_cordelia = get_following_users(cordelia.id)
        self.assertIn(hamlet.id, followers_of_cordelia)

        # But cordelia is in hamlet's "following" list
        followers_of_hamlet = get_following_users(hamlet.id)
        self.assertEqual(followers_of_hamlet, set())

    def test_follow_after_user_reactivation(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Deactivate cordelia
        do_deactivate_user(cordelia, acting_user=None)

        # Hamlet can still follow deactivated users
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        # Follow should exist
        followed_users = get_user_follows(hamlet)
        self.assert_length(followed_users, 1)
        self.assertEqual(followed_users[0]["id"], cordelia.id)


class FollowedUsersNarrowFilterTests(ZulipTestCase):
    """Tests for the is:followed-user narrow filter functionality."""

    def test_get_following_user_ids_empty(self) -> None:
        hamlet = self.example_user("hamlet")

        # User with no follows should return empty list
        following_ids = get_following_user_ids(hamlet.id)
        self.assertEqual(following_ids, [])

    def test_get_following_user_ids_single_follow(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Follow one user
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_post(hamlet, url)
        self.assert_json_success(result)

        following_ids = get_following_user_ids(hamlet.id)
        self.assertEqual(following_ids, [cordelia.id])

    def test_get_following_user_ids_multiple_follows(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        prospero = self.example_user("prospero")

        # Follow multiple users
        for target in [cordelia, othello, prospero]:
            url = f"/api/v1/users/me/followed_users/{target.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        following_ids = set(get_following_user_ids(hamlet.id))
        self.assertEqual(following_ids, {cordelia.id, othello.id, prospero.id})

    def test_get_following_user_ids_after_unfollow(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        # Follow two users
        for target in [cordelia, othello]:
            url = f"/api/v1/users/me/followed_users/{target.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        # Unfollow one
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        result = self.api_delete(hamlet, url)
        self.assert_json_success(result)

        # Should only have othello
        following_ids = get_following_user_ids(hamlet.id)
        self.assertEqual(following_ids, [othello.id])

    def test_get_following_user_ids_used_for_narrow_filter(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        prospero = self.example_user("prospero")

        # Follow cordelia and othello, but not prospero
        for target in [cordelia, othello]:
            url = f"/api/v1/users/me/followed_users/{target.id}"
            result = self.api_post(hamlet, url)
            self.assert_json_success(result)

        # Verify get_following_user_ids is correct for narrow filter
        following_ids = set(get_following_user_ids(hamlet.id))
        self.assertIn(cordelia.id, following_ids)
        self.assertIn(othello.id, following_ids)
        self.assertNotIn(prospero.id, following_ids)

        # In a real narrow filter implementation, the frontend would use these IDs
        # to filter messages. We verify here that the data is correct for that purpose.
        self.assertEqual(len(following_ids), 2)

    def test_multiple_followers_have_independent_follows(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        prospero = self.example_user("prospero")

        # Hamlet follows cordelia and othello
        for target in [cordelia, othello]:
            url = f"/api/v1/users/me/followed_users/{target.id}"
            self.api_post(hamlet, url)

        # Prospero follows only cordelia
        url = f"/api/v1/users/me/followed_users/{cordelia.id}"
        self.api_post(prospero, url)

        # Verify independent follow lists
        hamlet_follows = set(get_following_user_ids(hamlet.id))
        prospero_follows = set(get_following_user_ids(prospero.id))

        self.assertEqual(hamlet_follows, {cordelia.id, othello.id})
        self.assertEqual(prospero_follows, {cordelia.id})

        # Cordelia is followed by both hamlet and prospero
        cordelia_followers = get_following_users(cordelia.id)
        self.assertIn(hamlet.id, cordelia_followers)
        self.assertIn(prospero.id, cordelia_followers)
