from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest import mock

from django.utils.timezone import now as timezone_now

from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_topics import (
    get_topic_mutes,
    topic_has_visibility_policy,
)
from zerver.models import UserProfile, UserTopic, get_stream


class MutedTopicsTests(ZulipTestCase):
    def test_get_deactivated_muted_topic(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        stream = get_stream("Verona", user.realm)

        mock_date_muted = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()

        do_set_user_topic_visibility_policy(
            user,
            stream,
            "Verona3",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
            last_updated=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )

        stream.deactivated = True
        stream.save()

        self.assertNotIn((stream.name, "Verona3", mock_date_muted), get_topic_mutes(user))
        self.assertIn((stream.name, "Verona3", mock_date_muted), get_topic_mutes(user, True))

    def test_user_ids_muting_topic(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        realm = hamlet.realm
        stream = get_stream("Verona", realm)
        topic_name = "teST topic"
        date_muted = datetime(2020, 1, 1, tzinfo=timezone.utc)

        stream_topic_target = StreamTopicTarget(
            stream_id=stream.id,
            topic_name=topic_name,
        )

        user_ids = stream_topic_target.user_ids_with_visibility_policy(
            UserTopic.VisibilityPolicy.MUTED
        )
        self.assertEqual(user_ids, set())

        def mute_topic_for_user(user: UserProfile) -> None:
            do_set_user_topic_visibility_policy(
                user,
                stream,
                "test TOPIC",
                visibility_policy=UserTopic.VisibilityPolicy.MUTED,
                last_updated=date_muted,
            )

        mute_topic_for_user(hamlet)
        user_ids = stream_topic_target.user_ids_with_visibility_policy(
            UserTopic.VisibilityPolicy.MUTED
        )
        self.assertEqual(user_ids, {hamlet.id})
        hamlet_date_muted = UserTopic.objects.filter(
            user_profile=hamlet, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )[0].last_updated
        self.assertEqual(hamlet_date_muted, date_muted)

        mute_topic_for_user(cordelia)
        user_ids = stream_topic_target.user_ids_with_visibility_policy(
            UserTopic.VisibilityPolicy.MUTED
        )
        self.assertEqual(user_ids, {hamlet.id, cordelia.id})
        cordelia_date_muted = UserTopic.objects.filter(
            user_profile=cordelia, visibility_policy=UserTopic.VisibilityPolicy.MUTED
        )[0].last_updated
        self.assertEqual(cordelia_date_muted, date_muted)

    def test_add_muted_topic(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        stream = get_stream("Verona", user.realm)

        url = "/api/v1/users/me/subscriptions/muted_topics"

        payloads: List[Dict[str, object]] = [
            {"stream": stream.name, "topic": "Verona3", "op": "add"},
            {"stream_id": stream.id, "topic": "Verona3", "op": "add"},
        ]

        mock_date_muted = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
        for data in payloads:
            with mock.patch(
                "zerver.views.user_topics.timezone_now",
                return_value=datetime(2020, 1, 1, tzinfo=timezone.utc),
            ):
                result = self.api_patch(user, url, data)
                self.assert_json_success(result)

            self.assertIn((stream.name, "Verona3", mock_date_muted), get_topic_mutes(user))
            self.assertTrue(
                topic_has_visibility_policy(
                    user, stream.id, "verona3", UserTopic.VisibilityPolicy.MUTED
                )
            )

            do_set_user_topic_visibility_policy(
                user,
                stream,
                "Verona3",
                visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
            )

        assert stream.recipient is not None
        result = self.api_patch(user, url, data)

        # Now check that no error is raised when attempted to mute
        # an already muted topic. This should be case-insensitive.
        user_topic_count = UserTopic.objects.count()
        data["topic"] = "VERONA3"
        with self.assertLogs(level="INFO") as info_logs:
            result = self.api_patch(user, url, data)
            self.assert_json_success(result)
        self.assertEqual(
            info_logs.output[0],
            f"INFO:root:User {user.id} tried to set visibility_policy to its current value of {UserTopic.VisibilityPolicy.MUTED}",
        )
        # Verify that we didn't end up with duplicate UserTopic rows
        # with the two different cases after the previous API call.
        self.assertEqual(UserTopic.objects.count() - user_topic_count, 0)

    def test_remove_muted_topic(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)

        stream = get_stream("Verona", realm)

        url = "/api/v1/users/me/subscriptions/muted_topics"
        payloads: List[Dict[str, object]] = [
            {"stream": stream.name, "topic": "vERONA3", "op": "remove"},
            {"stream_id": stream.id, "topic": "vEroNA3", "op": "remove"},
        ]
        mock_date_muted = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()

        for data in payloads:
            do_set_user_topic_visibility_policy(
                user,
                stream,
                "Verona3",
                visibility_policy=UserTopic.VisibilityPolicy.MUTED,
                last_updated=datetime(2020, 1, 1, tzinfo=timezone.utc),
            )
            self.assertIn((stream.name, "Verona3", mock_date_muted), get_topic_mutes(user))

            result = self.api_patch(user, url, data)

            self.assert_json_success(result)
            self.assertNotIn((stream.name, "Verona3", mock_date_muted), get_topic_mutes(user))
            self.assertFalse(
                topic_has_visibility_policy(
                    user, stream.id, "verona3", UserTopic.VisibilityPolicy.MUTED
                )
            )

    def test_muted_topic_add_invalid(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)

        stream = get_stream("Verona", realm)
        do_set_user_topic_visibility_policy(
            user,
            stream,
            "Verona3",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
            last_updated=timezone_now(),
        )

        url = "/api/v1/users/me/subscriptions/muted_topics"

        data = {"stream_id": 999999999, "topic": "Verona3", "op": "add"}
        result = self.api_patch(user, url, data)
        self.assert_json_error(result, "Invalid stream ID")

        data = {"topic": "Verona3", "op": "add"}
        result = self.api_patch(user, url, data)
        self.assert_json_error(result, "Please supply 'stream'.")

        data = {"stream": stream.name, "stream_id": stream.id, "topic": "Verona3", "op": "add"}
        result = self.api_patch(user, url, data)
        self.assert_json_error(result, "Please choose one: 'stream' or 'stream_id'.")

    def test_muted_topic_remove_invalid(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)
        stream = get_stream("Verona", realm)

        url = "/api/v1/users/me/subscriptions/muted_topics"
        data: Dict[str, Any] = {"stream": "BOGUS", "topic": "Verona3", "op": "remove"}
        result = self.api_patch(user, url, data)
        self.assert_json_error(result, "Topic is not muted")

        # Check that removing mute from a topic for which the user
        # doesn't already have a visibility_policy doesn't cause an error.
        data = {"stream": stream.name, "topic": "BOGUS", "op": "remove"}
        with self.assertLogs(level="INFO") as info_logs:
            result = self.api_patch(user, url, data)
            self.assert_json_success(result)
        self.assertEqual(
            info_logs.output[0],
            f"INFO:root:User {user.id} tried to remove visibility_policy, which actually doesn't exist",
        )

        data = {"stream_id": 999999999, "topic": "BOGUS", "op": "remove"}
        result = self.api_patch(user, url, data)
        self.assert_json_error(result, "Topic is not muted")

        data = {"topic": "Verona3", "op": "remove"}
        result = self.api_patch(user, url, data)
        self.assert_json_error(result, "Please supply 'stream'.")

        data = {"stream": stream.name, "stream_id": stream.id, "topic": "Verona3", "op": "remove"}
        result = self.api_patch(user, url, data)
        self.assert_json_error(result, "Please choose one: 'stream' or 'stream_id'.")


class UnmutedTopicsTests(ZulipTestCase):
    def test_user_ids_unmuting_topic(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        realm = hamlet.realm
        stream = get_stream("Verona", realm)
        topic_name = "teST topic"
        date_unmuted = datetime(2020, 1, 1, tzinfo=timezone.utc)

        stream_topic_target = StreamTopicTarget(
            stream_id=stream.id,
            topic_name=topic_name,
        )

        user_ids = stream_topic_target.user_ids_with_visibility_policy(
            UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assertEqual(user_ids, set())

        def set_topic_visibility_for_user(user: UserProfile, visibility_policy: int) -> None:
            do_set_user_topic_visibility_policy(
                user,
                stream,
                "test TOPIC",
                visibility_policy=visibility_policy,
                last_updated=date_unmuted,
            )

        set_topic_visibility_for_user(hamlet, UserTopic.VisibilityPolicy.UNMUTED)
        set_topic_visibility_for_user(cordelia, UserTopic.VisibilityPolicy.MUTED)
        user_ids = stream_topic_target.user_ids_with_visibility_policy(
            UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assertEqual(user_ids, {hamlet.id})
        hamlet_date_unmuted = UserTopic.objects.filter(
            user_profile=hamlet, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )[0].last_updated
        self.assertEqual(hamlet_date_unmuted, date_unmuted)

        set_topic_visibility_for_user(cordelia, UserTopic.VisibilityPolicy.UNMUTED)
        user_ids = stream_topic_target.user_ids_with_visibility_policy(
            UserTopic.VisibilityPolicy.UNMUTED
        )
        self.assertEqual(user_ids, {hamlet.id, cordelia.id})
        cordelia_date_unmuted = UserTopic.objects.filter(
            user_profile=cordelia, visibility_policy=UserTopic.VisibilityPolicy.UNMUTED
        )[0].last_updated
        self.assertEqual(cordelia_date_unmuted, date_unmuted)
