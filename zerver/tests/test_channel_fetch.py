from typing import TYPE_CHECKING, Any

import orjson
from django.conf import settings
from django.test import override_settings
from typing_extensions import override

from zerver.actions.streams import (
    do_change_stream_group_based_setting,
    do_change_stream_permission,
    do_deactivate_stream,
)
from zerver.lib.create_user import create_user
from zerver.lib.email_mirror_helpers import encode_email_address, get_channel_email_token
from zerver.lib.subscription_info import gather_subscriptions, gather_subscriptions_helper
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message
from zerver.lib.types import (
    APIStreamDict,
    APISubscriptionDict,
    NeverSubscribedStreamDict,
    SubscriptionInfo,
    UserGroupMembersData,
    UserGroupMembersDict,
)
from zerver.models import NamedUserGroup, Realm, Stream, Subscription, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import get_system_bot

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def fix_expected_fields_for_stream_group_settings(expected_fields: set[str]) -> set[str]:
    for setting_name in Stream.stream_permission_group_settings:
        expected_fields -= {setting_name + "_id"}
        expected_fields |= {setting_name}

    return expected_fields


class GetStreamsTest(ZulipTestCase):
    def test_streams_api_for_bot_owners(self) -> None:
        hamlet = self.example_user("hamlet")
        test_bot = self.create_test_bot("foo", hamlet)
        assert test_bot is not None
        realm = get_realm("zulip")
        self.login_user(hamlet)

        # Check it correctly lists the bot owner's subs with
        # include_owner_subscribed=true
        filters = dict(
            include_owner_subscribed="true",
            include_public="false",
            include_subscribed="false",
        )
        with self.assert_database_query_count(7):
            result = self.api_get(test_bot, "/api/v1/streams", filters)
        owner_subs = self.api_get(hamlet, "/api/v1/users/me/subscriptions")

        json = self.assert_json_success(result)
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        self.assert_json_success(owner_subs)
        owner_subs_json = orjson.loads(owner_subs.content)

        self.assertEqual(
            sorted(s["name"] for s in json["streams"]),
            sorted(s["name"] for s in owner_subs_json["subscriptions"]),
        )

        # Check it correctly lists the bot owner's subs and the
        # bot's subs
        self.subscribe(test_bot, "Scotland")
        filters = dict(
            include_owner_subscribed="true",
            include_public="false",
            include_subscribed="true",
        )
        with self.assert_database_query_count(8):
            result = self.api_get(test_bot, "/api/v1/streams", filters)

        json = self.assert_json_success(result)
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        actual = sorted(s["name"] for s in json["streams"])
        expected = [s["name"] for s in owner_subs_json["subscriptions"]]
        expected.append("Scotland")
        expected.sort()

        self.assertEqual(actual, expected)

        # Check it correctly lists the bot owner's subs + all public streams
        self.make_stream("private_stream", realm=realm, invite_only=True)
        self.subscribe(test_bot, "private_stream")
        with self.assert_database_query_count(7):
            result = self.api_get(
                test_bot,
                "/api/v1/streams",
                {
                    "include_owner_subscribed": "true",
                    "include_public": "true",
                    "include_subscribed": "false",
                },
            )

        json = self.assert_json_success(result)
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        actual = sorted(s["name"] for s in json["streams"])
        expected = [s["name"] for s in owner_subs_json["subscriptions"]]
        expected.extend(["Rome", "Venice", "Scotland"])
        expected.sort()

        self.assertEqual(actual, expected)

        # Check it correctly lists the bot owner's subs + all public streams +
        # the bot's subs
        with self.assert_database_query_count(8):
            result = self.api_get(
                test_bot,
                "/api/v1/streams",
                {
                    "include_owner_subscribed": "true",
                    "include_public": "true",
                    "include_subscribed": "true",
                },
            )

        json = self.assert_json_success(result)
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        actual = sorted(s["name"] for s in json["streams"])
        expected = [s["name"] for s in owner_subs_json["subscriptions"]]
        expected.extend(["Rome", "Venice", "Scotland", "private_stream"])
        expected.sort()

        self.assertEqual(actual, expected)

        private_stream_2 = self.make_stream("private_stream_2", realm=realm, invite_only=True)
        private_stream_3 = self.make_stream("private_stream_3", realm=realm, invite_only=True)
        self.make_stream("private_stream_4", realm=realm, invite_only=True)
        test_bot_group_member_dict = UserGroupMembersData(
            direct_members=[test_bot.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            private_stream_2,
            "can_add_subscribers_group",
            test_bot_group_member_dict,
            acting_user=hamlet,
        )
        do_change_stream_group_based_setting(
            private_stream_3,
            "can_administer_channel_group",
            test_bot_group_member_dict,
            acting_user=hamlet,
        )
        # Check it correctly lists the bot owner's subs + the channels
        # bot has content access to.
        with self.assert_database_query_count(10):
            result = self.api_get(
                test_bot,
                "/api/v1/streams",
                {
                    "include_owner_subscribed": "true",
                    "include_can_access_content": "true",
                },
            )

        json = self.assert_json_success(result)
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        actual = sorted(s["name"] for s in json["streams"])
        expected = [s["name"] for s in owner_subs_json["subscriptions"]]
        expected.extend(["Rome", "Venice", "Scotland", "private_stream", "private_stream_2"])
        expected.sort()

        self.assertEqual(actual, expected)

    def test_all_streams_api(self) -> None:
        url = "/api/v1/streams"
        data = {"include_all": "true"}
        backward_compatible_data = {"include_all_active": "true"}

        # Normal user should be able to make this request and get all
        # the streams they have metadata access to.
        normal_user = self.example_user("cordelia")
        realm = normal_user.realm
        normal_user_group_members_dict = UserGroupMembersData(
            direct_members=[normal_user.id], direct_subgroups=[]
        )

        private_stream_1 = self.make_stream("private_stream_1", realm=realm, invite_only=True)
        private_stream_2 = self.make_stream("private_stream_2", realm=realm, invite_only=True)
        private_stream_3 = self.make_stream("private_stream_3", realm=realm, invite_only=True)
        self.make_stream("private_stream_4", realm=realm, invite_only=True)
        deactivated_public_stream = self.make_stream(
            "deactivated_public_stream", realm=realm, invite_only=False
        )
        do_deactivate_stream(deactivated_public_stream, acting_user=normal_user)

        self.subscribe(normal_user, private_stream_1.name)
        do_change_stream_group_based_setting(
            private_stream_2,
            "can_add_subscribers_group",
            normal_user_group_members_dict,
            acting_user=normal_user,
        )
        do_change_stream_group_based_setting(
            private_stream_3,
            "can_administer_channel_group",
            normal_user_group_members_dict,
            acting_user=normal_user,
        )

        result_stream_names: list[str] = [
            stream.name
            for stream in Stream.objects.filter(realm=realm, invite_only=False, deactivated=False)
        ]
        result_stream_names.extend(
            [private_stream_1.name, private_stream_2.name, private_stream_3.name]
        )
        with self.assert_database_query_count(8):
            result = self.api_get(normal_user, url, data)
        json = self.assert_json_success(result)
        self.assertEqual(sorted(s["name"] for s in json["streams"]), sorted(result_stream_names))

        # Normal user should be able to make this request and get all
        # the streams they have metadata access to.
        guest_user = self.example_user("polonius")
        guest_user_group_member_dict = UserGroupMembersData(
            direct_members=[guest_user.id], direct_subgroups=[]
        )

        self.subscribe(guest_user, private_stream_1.name)
        self.subscribe(guest_user, "design")
        do_change_stream_group_based_setting(
            private_stream_2,
            "can_add_subscribers_group",
            guest_user_group_member_dict,
            acting_user=normal_user,
        )
        do_change_stream_group_based_setting(
            get_stream("Rome", realm),
            "can_add_subscribers_group",
            guest_user_group_member_dict,
            acting_user=normal_user,
        )
        do_change_stream_group_based_setting(
            private_stream_3,
            "can_administer_channel_group",
            guest_user_group_member_dict,
            acting_user=normal_user,
        )
        do_change_stream_group_based_setting(
            get_stream("Denmark", realm),
            "can_administer_channel_group",
            guest_user_group_member_dict,
            acting_user=normal_user,
        )

        # Guest user should not gain metadata access to a channel via
        # `can_add_subscribers_group` or `can_administer_channel_group`
        # since `allow_everyone_group` if false for both of those groups.
        result_stream_names = ["Verona", "private_stream_1", "design", "Rome"]
        with self.assert_database_query_count(7):
            result = self.api_get(guest_user, url, data)
        json = self.assert_json_success(result)
        self.assertEqual(sorted(s["name"] for s in json["streams"]), sorted(result_stream_names))

        # Realm admin users can see all active streams if
        # `exclude_archived` is not set.
        admin_user = self.example_user("iago")
        self.assertTrue(admin_user.is_realm_admin)

        with self.assert_database_query_count(7):
            result = self.api_get(admin_user, url, data)
        json = self.assert_json_success(result)

        backward_compatible_result = self.api_get(admin_user, url, backward_compatible_data)
        json_for_backward_compatible_request = self.assert_json_success(backward_compatible_result)

        self.assertEqual(json, json_for_backward_compatible_request)

        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        stream_names = {s["name"] for s in json["streams"]}
        result_stream_names = [
            stream.name for stream in Stream.objects.filter(realm=realm, deactivated=False)
        ]
        self.assertEqual(
            sorted(stream_names),
            sorted(result_stream_names),
        )

        # Realm admin users can see all streams if `exclude_archived`
        # is set to false.
        data = {"include_all": "true", "exclude_archived": "false"}
        with self.assert_database_query_count(7):
            result = self.api_get(admin_user, url, data)
        json = self.assert_json_success(result)
        stream_names = {s["name"] for s in json["streams"]}
        result_stream_names = [stream.name for stream in Stream.objects.filter(realm=realm)]
        self.assertEqual(
            sorted(stream_names),
            sorted(result_stream_names),
        )

        # This case will not happen in practice, we are adding this
        # test block to add coverage for the case where
        # `get_metadata_access_streams` returns an empty list without
        # query if an empty list of streams is passed to it.
        all_active_streams = Stream.objects.filter(realm=realm, deactivated=False)
        for stream in all_active_streams:
            do_deactivate_stream(stream, acting_user=None)

        data = {"include_all": "true"}
        with self.assert_database_query_count(3):
            result = self.api_get(admin_user, url, data)
        json = self.assert_json_success(result)
        stream_names = {s["name"] for s in json["streams"]}
        self.assertEqual(stream_names, set())

    def test_public_streams_api(self) -> None:
        """
        Ensure that the query we use to get public streams successfully returns
        a list of streams
        """
        user = self.example_user("hamlet")
        realm = get_realm("zulip")
        self.login_user(user)

        # Check it correctly lists the user's subs with include_public=false
        result = self.api_get(user, "/api/v1/streams", {"include_public": "false"})
        result2 = self.api_get(user, "/api/v1/users/me/subscriptions")

        json = self.assert_json_success(result)

        self.assertIn("streams", json)

        self.assertIsInstance(json["streams"], list)

        self.assert_json_success(result2)
        json2 = orjson.loads(result2.content)

        self.assertEqual(
            sorted(s["name"] for s in json["streams"]),
            sorted(s["name"] for s in json2["subscriptions"]),
        )

        # Check it correctly lists all public streams with include_subscribed=false
        filters = dict(include_public="true", include_subscribed="false")
        result = self.api_get(user, "/api/v1/streams", filters)
        json = self.assert_json_success(result)
        all_streams = [
            stream.name for stream in Stream.objects.filter(realm=realm, invite_only=False)
        ]
        self.assertEqual(sorted(s["name"] for s in json["streams"]), sorted(all_streams))

    def test_include_can_access_content_streams_api(self) -> None:
        """
        Ensure that the query we use to get public streams successfully returns
        a list of streams
        """
        # Cordelia is not subscribed to private stream `core team`.
        user = self.example_user("cordelia")
        realm = get_realm("zulip")
        self.login_user(user)
        user_group_members_dict = UserGroupMembersData(
            direct_members=[user.id], direct_subgroups=[]
        )

        private_stream_1 = self.make_stream("private_stream_1", realm=realm, invite_only=True)
        private_stream_2 = self.make_stream("private_stream_2", realm=realm, invite_only=True)
        private_stream_3 = self.make_stream("private_stream_3", realm=realm, invite_only=True)
        self.make_stream("private_stream_4", realm=realm, invite_only=True)

        self.subscribe(user, private_stream_1.name)
        do_change_stream_group_based_setting(
            private_stream_2, "can_add_subscribers_group", user_group_members_dict, acting_user=user
        )
        do_change_stream_group_based_setting(
            private_stream_3,
            "can_administer_channel_group",
            user_group_members_dict,
            acting_user=user,
        )

        # Check it correctly lists all content access streams with
        # include_can_access_content=false
        filters = dict(include_can_access_content="true")
        with self.assert_database_query_count(8):
            result = self.api_get(user, "/api/v1/streams", filters)
        json = self.assert_json_success(result)
        result_streams = [
            stream.name for stream in Stream.objects.filter(realm=realm, invite_only=False)
        ]
        result_streams.extend([private_stream_1.name, private_stream_2.name])
        self.assertEqual(sorted(s["name"] for s in json["streams"]), sorted(result_streams))

    def test_get_single_stream_api(self) -> None:
        self.login("hamlet")
        realm = get_realm("zulip")
        denmark_stream = get_stream("Denmark", realm)
        result = self.client_get(f"/json/streams/{denmark_stream.id}")
        json = self.assert_json_success(result)
        self.assertEqual(json["stream"]["name"], "Denmark")
        self.assertEqual(json["stream"]["stream_id"], denmark_stream.id)

        result = self.client_get("/json/streams/9999")
        self.assert_json_error(result, "Invalid channel ID")

        private_stream = self.make_stream("private_stream", invite_only=True)
        self.subscribe(self.example_user("cordelia"), "private_stream")

        # Non-admins cannot access unsubscribed private streams.
        result = self.client_get(f"/json/streams/{private_stream.id}")
        self.assert_json_error(result, "Invalid channel ID")

        self.login("iago")
        result = self.client_get(f"/json/streams/{private_stream.id}")
        json = self.assert_json_success(result)
        self.assertEqual(json["stream"]["name"], "private_stream")
        self.assertEqual(json["stream"]["stream_id"], private_stream.id)

        self.login("cordelia")
        result = self.client_get(f"/json/streams/{private_stream.id}")
        json = self.assert_json_success(result)
        self.assertEqual(json["stream"]["name"], "private_stream")
        self.assertEqual(json["stream"]["stream_id"], private_stream.id)

    def test_get_stream_email_address(self) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        polonius = self.example_user("polonius")
        realm = get_realm("zulip")
        email_gateway_bot = get_system_bot(settings.EMAIL_GATEWAY_BOT, realm.id)
        denmark_stream = get_stream("Denmark", realm)
        result = self.client_get(f"/json/streams/{denmark_stream.id}/email_address")
        json = self.assert_json_success(result)
        email_token = get_channel_email_token(
            denmark_stream, creator=hamlet, sender=email_gateway_bot
        )
        hamlet_denmark_email = encode_email_address(
            denmark_stream.name, email_token, show_sender=True
        )
        self.assertEqual(json["email"], hamlet_denmark_email)

        self.login("polonius")
        result = self.client_get(f"/json/streams/{denmark_stream.id}/email_address")
        self.assert_json_error(result, "Invalid channel ID")

        self.subscribe(polonius, "Denmark")
        result = self.client_get(f"/json/streams/{denmark_stream.id}/email_address")
        json = self.assert_json_success(result)
        email_token = get_channel_email_token(
            denmark_stream, creator=polonius, sender=email_gateway_bot
        )
        polonius_denmark_email = encode_email_address(
            denmark_stream.name, email_token, show_sender=True
        )
        self.assertEqual(json["email"], polonius_denmark_email)

        do_change_stream_permission(
            denmark_stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=iago,
        )
        self.login("hamlet")
        result = self.client_get(f"/json/streams/{denmark_stream.id}/email_address")
        json = self.assert_json_success(result)
        self.assertEqual(json["email"], hamlet_denmark_email)

        self.unsubscribe(hamlet, "Denmark")
        result = self.client_get(f"/json/streams/{denmark_stream.id}/email_address")
        self.assert_json_error(result, "Invalid channel ID")

        self.login("iago")
        result = self.client_get(f"/json/streams/{denmark_stream.id}/email_address")
        json = self.assert_json_success(result)
        email_token = get_channel_email_token(
            denmark_stream, creator=iago, sender=email_gateway_bot
        )
        iago_denmark_email = encode_email_address(
            denmark_stream.name, email_token, show_sender=True
        )
        self.assertEqual(json["email"], iago_denmark_email)

        self.unsubscribe(iago, "Denmark")
        result = self.client_get(f"/json/streams/{denmark_stream.id}/email_address")
        self.assert_json_error(result, "Invalid channel ID")

    def test_guest_user_access_to_streams(self) -> None:
        user_profile = self.example_user("polonius")
        self.login_user(user_profile)
        self.assertEqual(user_profile.role, UserProfile.ROLE_GUEST)

        # Get all the streams that Polonius has access to (subscribed + web-public streams)
        result = self.client_get("/json/streams", {"include_web_public": "true"})
        streams = self.assert_json_success(result)["streams"]
        sub_info = gather_subscriptions_helper(user_profile)

        subscribed = sub_info.subscriptions
        unsubscribed = sub_info.unsubscribed
        never_subscribed = sub_info.never_subscribed

        self.assert_length(streams, len(subscribed) + len(unsubscribed) + len(never_subscribed))
        stream_names = [stream["name"] for stream in streams]
        expected_stream_names = [stream["name"] for stream in subscribed + unsubscribed]
        expected_stream_names += [stream["name"] for stream in never_subscribed]
        self.assertEqual(set(stream_names), set(expected_stream_names))


class StreamIdTest(ZulipTestCase):
    def test_get_stream_id(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        stream = gather_subscriptions(user)[0][0]
        result = self.client_get("/json/get_stream_id", {"stream": stream["name"]})
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["stream_id"], stream["stream_id"])

    def test_get_stream_id_wrong_name(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.client_get("/json/get_stream_id", {"stream": "wrongname"})
        self.assert_json_error(result, "Invalid channel name 'wrongname'")


class GetSubscribersTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("hamlet")
        self.login_user(self.user_profile)

    def test_api_fields(self) -> None:
        """Verify that all the fields from `Stream.API_FIELDS` and `Subscription.API_FIELDS` present
        in `APIStreamDict` and `APISubscriptionDict`, respectively.
        """
        expected_fields = set(Stream.API_FIELDS) | {"stream_id", "is_archived"}
        expected_fields -= {"id", "deactivated"}
        expected_fields = fix_expected_fields_for_stream_group_settings(expected_fields)

        stream_dict_fields = set(APIStreamDict.__annotations__.keys())
        computed_fields = {
            "is_announcement_only",
            "is_default",
            "stream_post_policy",
            "stream_weekly_traffic",
        }

        self.assertEqual(stream_dict_fields - computed_fields, expected_fields)

        expected_fields = set(Subscription.API_FIELDS)

        subscription_dict_fields = set(APISubscriptionDict.__annotations__.keys())
        computed_fields = {"in_home_view", "email_address", "stream_weekly_traffic", "subscribers"}
        # `APISubscriptionDict` is a subclass of `APIStreamDict`, therefore having all the
        # fields in addition to the computed fields and `Subscription.API_FIELDS` that
        # need to be excluded here.
        self.assertEqual(
            subscription_dict_fields - computed_fields - stream_dict_fields,
            expected_fields,
        )

    def verify_sub_fields(self, sub_data: SubscriptionInfo) -> None:
        other_fields = {
            "is_archived",
            "is_announcement_only",
            "in_home_view",
            "stream_id",
            "stream_post_policy",
            "stream_weekly_traffic",
            "subscribers",
        }

        expected_fields = set(Stream.API_FIELDS) | set(Subscription.API_FIELDS) | other_fields
        expected_fields -= {"id", "deactivated"}
        expected_fields = fix_expected_fields_for_stream_group_settings(expected_fields)

        for lst in [sub_data.subscriptions, sub_data.unsubscribed]:
            for sub in lst:
                self.assertEqual(set(sub), expected_fields)

        other_fields = {
            "is_archived",
            "is_announcement_only",
            "stream_id",
            "stream_post_policy",
            "stream_weekly_traffic",
            "subscribers",
        }

        expected_fields = set(Stream.API_FIELDS) | other_fields
        expected_fields -= {"id", "deactivated"}
        expected_fields = fix_expected_fields_for_stream_group_settings(expected_fields)

        for never_sub in sub_data.never_subscribed:
            self.assertEqual(set(never_sub), expected_fields)

    def assert_user_got_subscription_notification(
        self, user: UserProfile, expected_msg: str
    ) -> None:
        # verify that the user was sent a message informing them about the subscription
        realm = user.realm
        msg = most_recent_message(user)
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id, self.notification_bot(realm).id)

        def non_ws(s: str) -> str:
            return s.replace("\n", "").replace(" ", "")

        assert msg.rendered_content is not None
        self.assertEqual(non_ws(msg.rendered_content), non_ws(expected_msg))

    def check_well_formed_result(
        self, result: dict[str, Any], stream_name: str, realm: Realm
    ) -> None:
        """
        A successful call to get_subscribers returns the list of subscribers in
        the form:

        {"msg": "",
         "result": "success",
         "subscribers": [hamlet_user.id, prospero_user.id]}
        """
        self.assertIn("subscribers", result)
        self.assertIsInstance(result["subscribers"], list)
        true_subscribers = [
            user_profile.id for user_profile in self.users_subscribed_to_stream(stream_name, realm)
        ]
        self.assertEqual(sorted(result["subscribers"]), sorted(true_subscribers))

    def make_subscriber_request(
        self, stream_id: int, user: UserProfile | None = None
    ) -> "TestHttpResponse":
        if user is None:
            user = self.user_profile
        return self.api_get(user, f"/api/v1/streams/{stream_id}/members")

    def make_successful_subscriber_request(self, stream_name: str) -> None:
        stream_id = get_stream(stream_name, self.user_profile.realm).id
        result = self.make_subscriber_request(stream_id)
        response_dict = self.assert_json_success(result)
        self.check_well_formed_result(response_dict, stream_name, self.user_profile.realm)

    def test_subscriber(self) -> None:
        """
        get_subscribers returns the list of subscribers.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]["name"]
        self.make_successful_subscriber_request(stream_name)

    @override_settings(MIN_PARTIAL_SUBSCRIBERS_CHANNEL_SIZE=5)
    def test_gather_partial_subscriptions(self) -> None:
        othello = self.example_user("othello")
        idle_users = [
            create_user(
                email=f"original_user{i}@zulip.com",
                password=None,
                realm=othello.realm,
                full_name=f"Full Name {i}",
            )
            for i in range(5)
        ]
        for user in idle_users:
            user.long_term_idle = True
            user.save()
        bot = self.create_test_bot("bot", othello, "Foo Bot")

        stream_names = [
            "never_subscribed_only_bots",
            "never_subscribed_many_more_than_bots",
            "unsubscribed_only_bots",
            "subscribed_more_than_bots_including_idle",
            "subscribed_many_more_than_bots",
        ]
        for stream_name in stream_names:
            self.make_stream(stream_name)

        self.subscribe_via_post(
            self.user_profile,
            ["never_subscribed_only_bots"],
            dict(principals=orjson.dumps([bot.id]).decode()),
        )
        self.subscribe_via_post(
            self.user_profile,
            ["never_subscribed_many_more_than_bots"],
            dict(
                principals=orjson.dumps(
                    [bot.id, othello.id] + [user.id for user in idle_users]
                ).decode()
            ),
        )
        self.subscribe_via_post(
            self.user_profile,
            ["unsubscribed_only_bots"],
            dict(principals=orjson.dumps([bot.id, self.user_profile.id]).decode()),
        )
        self.unsubscribe(
            self.user_profile,
            "unsubscribed_only_bots",
        )
        self.subscribe_via_post(
            self.user_profile,
            ["subscribed_more_than_bots_including_idle"],
            dict(
                principals=orjson.dumps(
                    [bot.id, othello.id, self.user_profile.id, idle_users[0].id]
                ).decode()
            ),
        )
        self.subscribe_via_post(
            self.user_profile,
            ["subscribed_many_more_than_bots"],
            dict(
                principals=orjson.dumps(
                    [bot.id, othello.id, self.user_profile.id] + [user.id for user in idle_users]
                ).decode()
            ),
        )

        with self.assert_database_query_count(9):
            sub_data = gather_subscriptions_helper(self.user_profile, include_subscribers="partial")
            never_subscribed_streams = sub_data.never_subscribed
            unsubscribed_streams = sub_data.unsubscribed
            subscribed_streams = sub_data.subscriptions
        self.assertGreaterEqual(len(never_subscribed_streams), 2)
        self.assertGreaterEqual(len(unsubscribed_streams), 1)
        self.assertGreaterEqual(len(subscribed_streams), 1)

        # Streams with only bots have sent all of their subscribers,
        # since we always send bots. We tell the client it doesn't
        # need to fetch more, by filling "subscribers" instead
        # of "partial_subscribers". If there are non-bot subscribers,
        # a partial fetch will return only partial subscribers.

        for sub in never_subscribed_streams:
            if sub["name"] == "never_subscribed_only_bots":
                self.assert_length(sub["subscribers"], 1)
                self.assertIsNone(sub.get("partial_subscribers"))
                continue
            if sub["name"] == "never_subscribed_many_more_than_bots":
                # the bot and Othello (who is not long_term_idle)
                self.assert_length(sub["partial_subscribers"], 2)
                self.assertIsNone(sub.get("subscribers"))

        for sub in unsubscribed_streams:
            if sub["name"] == "unsubscribed_only_bots":
                self.assert_length(sub["subscribers"], 1)
                self.assertIsNone(sub.get("partial_subscribers"))
                break

        for sub in subscribed_streams:
            # fewer than MIN_PARTIAL_SUBSCRIBERS_CHANNEL_SIZE subscribers,
            # so we get all of them
            if sub["name"] == "subscribed_more_than_bots_including_idle":
                self.assertIsNone(sub.get("partial_subscribers"))
                self.assert_length(sub["subscribers"], 4)
                continue
            if sub["name"] == "subscribed_many_more_than_bots":
                # the bot, Othello (who is not long_term_idle), and current user
                self.assert_length(sub["partial_subscribers"], 3)
                self.assertIsNone(sub.get("subscribers"))

    def test_gather_subscriptions(self) -> None:
        """
        gather_subscriptions returns correct results with only 3 queries

        (We also use this test to verify subscription notifications to
        folks who get subscribed to streams.)
        """
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        polonius = self.example_user("polonius")
        realm = hamlet.realm

        stream_names = [f"stream_{i}" for i in range(10)]
        streams: list[Stream] = [self.make_stream(stream_name) for stream_name in stream_names]

        users_to_subscribe = [
            self.user_profile.id,
            othello.id,
            cordelia.id,
            polonius.id,
        ]

        with self.assert_database_query_count(55):
            self.subscribe_via_post(
                self.user_profile,
                stream_names,
                dict(principals=orjson.dumps(users_to_subscribe).decode()),
            )

        rendered_stream_list = ""
        for stream in streams:
            rendered_stream_list = (
                rendered_stream_list
                + f"""<li><a class="stream" data-stream-id="{stream.id}" href="/#narrow/channel/{stream.id}-{stream.name}">#{stream.name}</a></li>\n"""
            )
        msg = f"""
            <p><span class="user-mention silent" data-user-id="{hamlet.id}">King Hamlet</span> subscribed you to the following channels:</p>
            <ul>
            {rendered_stream_list}
            </ul>
            """

        for user in [cordelia, othello, polonius]:
            self.assert_user_got_subscription_notification(user, msg)

        # Subscribe ourself first.
        self.subscribe_via_post(
            self.user_profile,
            ["stream_invite_only_1"],
            dict(principals=orjson.dumps([self.user_profile.id]).decode()),
            invite_only=True,
        )

        # Now add in other users, and this should trigger messages
        # to notify the user.
        self.subscribe_via_post(
            self.user_profile,
            ["stream_invite_only_1"],
            dict(principals=orjson.dumps(users_to_subscribe).decode()),
            invite_only=True,
        )

        stream_invite_only_1 = get_stream("stream_invite_only_1", realm)
        msg = f"""
            <p><span class="user-mention silent" data-user-id="{hamlet.id}">King Hamlet</span> subscribed you to <a class="stream" data-stream-id="{stream_invite_only_1.id}" href="/#narrow/channel/{stream_invite_only_1.id}-{stream_invite_only_1.name}">#{stream_invite_only_1.name}</a>.</p>
            """
        for user in [cordelia, othello, polonius]:
            self.assert_user_got_subscription_notification(user, msg)

        with self.assert_database_query_count(9):
            subscribed_streams, _ = gather_subscriptions(
                self.user_profile, include_subscribers=True
            )
        self.assertGreaterEqual(len(subscribed_streams), 11)
        for sub in subscribed_streams:
            if not sub["name"].startswith("stream_"):
                continue
            self.assert_length(sub["subscribers"], len(users_to_subscribe))

        # Test query count when setting is set to anonymous group.
        stream = get_stream("stream_1", realm)
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        setting_group_members_dict = UserGroupMembersData(
            direct_members=[hamlet.id], direct_subgroups=[admins_group.id]
        )
        do_change_stream_group_based_setting(
            stream,
            "can_remove_subscribers_group",
            setting_group_members_dict,
            acting_user=hamlet,
        )
        stream = get_stream("stream_2", realm)
        setting_group_members_dict = UserGroupMembersData(
            direct_members=[cordelia.id], direct_subgroups=[admins_group.id]
        )
        do_change_stream_group_based_setting(
            stream,
            "can_remove_subscribers_group",
            setting_group_members_dict,
            acting_user=hamlet,
        )

        with self.assert_database_query_count(9):
            subscribed_streams, _ = gather_subscriptions(
                self.user_profile, include_subscribers=True
            )
        self.assertGreaterEqual(len(subscribed_streams), 11)
        for sub in subscribed_streams:
            if not sub["name"].startswith("stream_"):
                continue
            self.assert_length(sub["subscribers"], len(users_to_subscribe))
            if sub["name"] == "stream_1":
                self.assertEqual(
                    sub["can_remove_subscribers_group"],
                    UserGroupMembersDict(
                        direct_members=[hamlet.id],
                        direct_subgroups=[admins_group.id],
                    ),
                )
            elif sub["name"] == "stream_2":
                self.assertEqual(
                    sub["can_remove_subscribers_group"],
                    UserGroupMembersDict(
                        direct_members=[cordelia.id],
                        direct_subgroups=[admins_group.id],
                    ),
                )
            else:
                self.assertEqual(sub["can_remove_subscribers_group"], admins_group.id)

    def test_stream_post_policy_values_in_subscription_objects(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        desdemona = self.example_user("desdemona")

        streams = [f"stream_{i}" for i in range(6)]
        for stream_name in streams:
            self.make_stream(stream_name)

        realm = hamlet.realm
        self.subscribe_via_post(
            hamlet,
            streams,
            dict(principals=orjson.dumps([hamlet.id, cordelia.id]).decode()),
        )

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        full_members_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )

        stream = get_stream("stream_1", realm)
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", admins_group, acting_user=desdemona
        )

        stream = get_stream("stream_2", realm)
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", members_group, acting_user=desdemona
        )

        stream = get_stream("stream_3", realm)
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", full_members_group, acting_user=desdemona
        )

        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)
        stream = get_stream("stream_4", realm)
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", hamletcharacters_group, acting_user=desdemona
        )

        setting_group_members_dict = UserGroupMembersData(
            direct_members=[cordelia.id], direct_subgroups=[admins_group.id]
        )
        stream = get_stream("stream_5", realm)
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", setting_group_members_dict, acting_user=desdemona
        )

        with self.assert_database_query_count(9):
            subscribed_streams, _ = gather_subscriptions(hamlet, include_subscribers=True)

        [stream_1_sub] = [sub for sub in subscribed_streams if sub["name"] == "stream_1"]
        self.assertEqual(stream_1_sub["can_send_message_group"], admins_group.id)
        self.assertEqual(stream_1_sub["stream_post_policy"], Stream.STREAM_POST_POLICY_ADMINS)

        [stream_2_sub] = [sub for sub in subscribed_streams if sub["name"] == "stream_2"]
        self.assertEqual(stream_2_sub["can_send_message_group"], members_group.id)
        self.assertEqual(stream_2_sub["stream_post_policy"], Stream.STREAM_POST_POLICY_EVERYONE)

        [stream_3_sub] = [sub for sub in subscribed_streams if sub["name"] == "stream_3"]
        self.assertEqual(stream_3_sub["can_send_message_group"], full_members_group.id)
        self.assertEqual(
            stream_3_sub["stream_post_policy"], Stream.STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS
        )

        [stream_4_sub] = [sub for sub in subscribed_streams if sub["name"] == "stream_4"]
        self.assertEqual(stream_4_sub["can_send_message_group"], hamletcharacters_group.id)
        self.assertEqual(stream_4_sub["stream_post_policy"], Stream.STREAM_POST_POLICY_EVERYONE)

        [stream_5_sub] = [sub for sub in subscribed_streams if sub["name"] == "stream_5"]
        self.assertEqual(
            stream_5_sub["can_send_message_group"],
            UserGroupMembersDict(
                direct_members=[cordelia.id],
                direct_subgroups=[admins_group.id],
            ),
        )
        self.assertEqual(stream_5_sub["stream_post_policy"], Stream.STREAM_POST_POLICY_EVERYONE)

    def test_never_subscribed_streams(self) -> None:
        """
        Check never_subscribed streams are fetched correctly and not include invite_only streams,
        or invite_only and public streams to guest users.
        """
        realm = get_realm("zulip")
        users_to_subscribe = [
            self.example_user("othello").id,
            self.example_user("cordelia").id,
        ]

        public_streams = [
            "test_stream_public_1",
            "test_stream_public_2",
            "test_stream_public_3",
            "test_stream_public_4",
            "test_stream_public_5",
        ]

        private_streams = [
            "test_stream_invite_only_1",
            "test_stream_invite_only_2",
        ]

        web_public_streams = [
            "test_stream_web_public_1",
            "test_stream_web_public_2",
        ]

        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", is_system_group=True, realm=realm
        )

        def create_public_streams() -> None:
            for stream_name in public_streams:
                self.make_stream(stream_name, realm=realm)

            self.subscribe_via_post(
                self.user_profile,
                public_streams,
                dict(
                    principals=orjson.dumps(users_to_subscribe).decode(),
                    can_administer_channel_group=nobody_group.id,
                ),
            )

        create_public_streams()

        def create_web_public_streams() -> None:
            for stream_name in web_public_streams:
                self.make_stream(stream_name, realm=realm, is_web_public=True)

            ret = self.subscribe_via_post(
                self.user_profile,
                web_public_streams,
                dict(
                    principals=orjson.dumps(users_to_subscribe).decode(),
                    can_administer_channel_group=nobody_group.id,
                ),
            )
            self.assert_json_success(ret)

        create_web_public_streams()

        def create_private_streams() -> None:
            self.subscribe_via_post(
                self.user_profile,
                private_streams,
                dict(
                    principals=orjson.dumps(users_to_subscribe).decode(),
                    can_administer_channel_group=nobody_group.id,
                ),
                invite_only=True,
            )

        create_private_streams()

        def get_never_subscribed(query_count: int = 9) -> list[NeverSubscribedStreamDict]:
            with self.assert_database_query_count(query_count):
                sub_data = gather_subscriptions_helper(self.user_profile)
                self.verify_sub_fields(sub_data)
            never_subscribed = sub_data.never_subscribed

            # Ignore old streams.
            never_subscribed = [dct for dct in never_subscribed if dct["name"].startswith("test_")]
            return never_subscribed

        never_subscribed = get_never_subscribed()

        # Invite only stream should not be there in never_subscribed streams
        self.assert_length(never_subscribed, len(public_streams) + len(web_public_streams))
        for stream_dict in never_subscribed:
            name = stream_dict["name"]
            self.assertFalse("invite_only" in name)
            self.assert_length(stream_dict["subscribers"], len(users_to_subscribe))

        # Send private stream subscribers to all realm admins.
        def test_realm_admin_case() -> None:
            self.user_profile.role = UserProfile.ROLE_REALM_ADMINISTRATOR
            # Test realm admins can get never subscribed private stream's subscribers.
            never_subscribed = get_never_subscribed(7)

            self.assertEqual(
                len(never_subscribed),
                len(public_streams) + len(private_streams) + len(web_public_streams),
            )
            for stream_dict in never_subscribed:
                self.assert_length(stream_dict["subscribers"], len(users_to_subscribe))

        test_realm_admin_case()

        # Send private stream subscribers to all realm admins.
        def test_channel_admin_case() -> None:
            self.user_profile.role = UserProfile.ROLE_MEMBER
            user_group_members_dict = UserGroupMembersData(
                direct_members=[self.user_profile.id], direct_subgroups=[]
            )
            do_change_stream_group_based_setting(
                get_stream("test_stream_invite_only_1", realm),
                "can_administer_channel_group",
                user_group_members_dict,
                acting_user=self.user_profile,
            )
            # Test channel admins can get never subscribed private stream's subscribers.
            never_subscribed = get_never_subscribed()

            self.assertEqual(
                len(never_subscribed),
                len(public_streams) + 1 + len(web_public_streams),
            )
            for stream_dict in never_subscribed:
                self.assert_length(stream_dict["subscribers"], len(users_to_subscribe))

        test_channel_admin_case()

        def test_can_add_subscribers_case() -> None:
            self.user_profile.role = UserProfile.ROLE_MEMBER
            user_group_members_dict = UserGroupMembersData(
                direct_members=[self.user_profile.id], direct_subgroups=[]
            )
            do_change_stream_group_based_setting(
                get_stream("test_stream_invite_only_1", realm),
                "can_add_subscribers_group",
                user_group_members_dict,
                acting_user=self.user_profile,
            )
            # Test channel admins can get never subscribed private stream's subscribers.
            never_subscribed = get_never_subscribed()

            self.assertEqual(
                len(never_subscribed),
                len(public_streams) + 1 + len(web_public_streams),
            )
            for stream_dict in never_subscribed:
                self.assert_length(stream_dict["subscribers"], len(users_to_subscribe))

        test_can_add_subscribers_case()

        def test_guest_user_case() -> None:
            self.user_profile.role = UserProfile.ROLE_GUEST
            helper_result = gather_subscriptions_helper(self.user_profile)
            self.verify_sub_fields(helper_result)
            sub = helper_result.subscriptions
            unsub = helper_result.unsubscribed
            never_sub = helper_result.never_subscribed

            # It's +1 because of the stream Rome.
            self.assert_length(never_sub, len(web_public_streams) + 1)
            sub_ids = [stream["stream_id"] for stream in sub]
            unsub_ids = [stream["stream_id"] for stream in unsub]

            for stream_dict in never_sub:
                self.assertTrue(stream_dict["is_web_public"])
                self.assertTrue(stream_dict["stream_id"] not in sub_ids)
                self.assertTrue(stream_dict["stream_id"] not in unsub_ids)

                # The Rome stream has is_web_public=True, with default
                # subscribers not set up by this test, so we do the
                # following check only for the streams we created.
                if stream_dict["name"] in web_public_streams:
                    self.assert_length(stream_dict["subscribers"], len(users_to_subscribe))

        test_guest_user_case()

    def test_gather_subscribed_streams_for_guest_user(self) -> None:
        guest_user = self.example_user("polonius")

        stream_name_sub = "public_stream_1"
        self.make_stream(stream_name_sub, realm=get_realm("zulip"))
        self.subscribe(guest_user, stream_name_sub)

        stream_name_unsub = "public_stream_2"
        self.make_stream(stream_name_unsub, realm=get_realm("zulip"))
        self.subscribe(guest_user, stream_name_unsub)
        self.unsubscribe(guest_user, stream_name_unsub)

        stream_name_never_sub = "public_stream_3"
        self.make_stream(stream_name_never_sub, realm=get_realm("zulip"))

        normal_user = self.example_user("aaron")
        self.subscribe(normal_user, stream_name_sub)
        self.subscribe(normal_user, stream_name_unsub)
        self.subscribe(normal_user, stream_name_unsub)

        helper_result = gather_subscriptions_helper(guest_user)
        self.verify_sub_fields(helper_result)
        subs = helper_result.subscriptions
        neversubs = helper_result.never_subscribed

        # Guest users get info about subscribed public stream's subscribers
        expected_stream_exists = False
        for sub in subs:
            if sub["name"] == stream_name_sub:
                expected_stream_exists = True
                self.assert_length(sub["subscribers"], 2)
        self.assertTrue(expected_stream_exists)

        # Guest user only get data about never subscribed streams if they're
        # web-public.
        for stream in neversubs:
            self.assertTrue(stream["is_web_public"])

        # Guest user only get data about never subscribed web-public streams
        self.assert_length(neversubs, 1)

    def test_api_fields_present(self) -> None:
        user = self.example_user("cordelia")

        sub_data = gather_subscriptions_helper(user)
        subscribed = sub_data.subscriptions
        self.assertGreaterEqual(len(subscribed), 1)
        self.verify_sub_fields(sub_data)

    def test_previously_subscribed_private_streams(self) -> None:
        admin_user = self.example_user("iago")
        non_admin_user = self.example_user("cordelia")
        guest_user = self.example_user("polonius")
        stream_name = "private_stream"

        stream = self.make_stream(stream_name, realm=get_realm("zulip"), invite_only=True)
        self.subscribe(admin_user, stream_name)
        self.subscribe(non_admin_user, stream_name)
        self.subscribe(guest_user, stream_name)
        self.subscribe(self.example_user("othello"), stream_name)

        self.unsubscribe(admin_user, stream_name)
        self.unsubscribe(non_admin_user, stream_name)
        self.unsubscribe(guest_user, stream_name)

        # Test admin user gets previously subscribed private stream's subscribers.
        sub_data = gather_subscriptions_helper(admin_user)
        self.verify_sub_fields(sub_data)
        unsubscribed_streams = sub_data.unsubscribed
        self.assert_length(unsubscribed_streams, 1)
        self.assert_length(unsubscribed_streams[0]["subscribers"], 1)

        # Test non-admin users cannot get previously subscribed private stream's subscribers.
        sub_data = gather_subscriptions_helper(non_admin_user)
        self.verify_sub_fields(sub_data)
        unsubscribed_streams = sub_data.unsubscribed
        self.assert_length(unsubscribed_streams, 0)

        # Test channel admin gets previously subscribed private stream's subscribers.
        non_admin_user_group_members_dict = UserGroupMembersData(
            direct_members=[non_admin_user.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            non_admin_user_group_members_dict,
            acting_user=admin_user,
        )
        sub_data = gather_subscriptions_helper(non_admin_user)
        self.verify_sub_fields(sub_data)
        unsubscribed_streams = sub_data.unsubscribed
        self.assert_length(unsubscribed_streams, 1)
        self.assert_length(unsubscribed_streams[0]["subscribers"], 1)

        sub_data = gather_subscriptions_helper(guest_user)
        self.verify_sub_fields(sub_data)
        unsubscribed_streams = sub_data.unsubscribed
        self.assert_length(unsubscribed_streams, 0)

    def test_previously_subscribed_public_streams(self) -> None:
        public_stream_name = "public_stream"
        web_public_stream_name = "web_public_stream"
        guest_user = self.example_user("polonius")
        member_user = self.example_user("hamlet")

        self.make_stream(public_stream_name, realm=get_realm("zulip"))
        self.make_stream(web_public_stream_name, realm=get_realm("zulip"), is_web_public=True)

        for stream_name in [public_stream_name, web_public_stream_name]:
            self.subscribe(guest_user, stream_name)
            self.subscribe(member_user, stream_name)
            self.subscribe(self.example_user("othello"), stream_name)

        for stream_name in [public_stream_name, web_public_stream_name]:
            self.unsubscribe(guest_user, stream_name)
            self.unsubscribe(member_user, stream_name)

        # Test member user gets previously subscribed public stream and its subscribers.
        sub_data = gather_subscriptions_helper(member_user)
        self.verify_sub_fields(sub_data)
        unsubscribed_streams = sub_data.unsubscribed
        self.assert_length(unsubscribed_streams, 2)
        self.assert_length(unsubscribed_streams[0]["subscribers"], 1)
        self.assert_length(unsubscribed_streams[1]["subscribers"], 1)

        # Test guest users cannot get previously subscribed public stream but can get
        # web-public stream and its subscribers.
        sub_data = gather_subscriptions_helper(guest_user)
        self.verify_sub_fields(sub_data)
        unsubscribed_streams = sub_data.unsubscribed
        self.assert_length(unsubscribed_streams, 1)
        self.assertEqual(unsubscribed_streams[0]["is_web_public"], True)
        self.assert_length(unsubscribed_streams[0]["subscribers"], 1)

    def test_gather_subscriptions_mit(self) -> None:
        """
        gather_subscriptions returns correct results with only 3 queries
        """
        # Subscribe only ourself because invites are disabled on mit.edu
        mit_user_profile = self.mit_user("starnine")
        user_id = mit_user_profile.id
        users_to_subscribe = [user_id, self.mit_user("espuser").id]
        for email in users_to_subscribe:
            stream = self.subscribe(mit_user_profile, "mit_stream")
            self.assertTrue(stream.is_in_zephyr_realm)

        self.subscribe_via_post(
            mit_user_profile,
            ["mit_invite_only"],
            dict(principals=orjson.dumps(users_to_subscribe).decode()),
            invite_only=True,
            subdomain="zephyr",
        )

        with self.assert_database_query_count(8):
            subscribed_streams, _ = gather_subscriptions(mit_user_profile, include_subscribers=True)

        self.assertGreaterEqual(len(subscribed_streams), 2)
        for sub in subscribed_streams:
            if not sub["name"].startswith("mit_"):
                raise AssertionError("Unexpected stream!")
            if sub["name"] == "mit_invite_only":
                self.assert_length(sub["subscribers"], len(users_to_subscribe))
            else:
                self.assert_length(sub["subscribers"], 0)
            self.assertIsNone(sub["stream_weekly_traffic"])

        # Create a web-public stream to test never_subscried data.
        self.make_stream("mit_stream_2", realm=mit_user_profile.realm, is_web_public=True)
        self.make_stream("mit_stream_3", realm=mit_user_profile.realm)

        sub_info = gather_subscriptions_helper(mit_user_profile, include_subscribers=True)
        never_subscribed_streams = sub_info.never_subscribed
        # Users in zephyr mirror realm can only access web-public never subscribed streams.
        self.assert_length(never_subscribed_streams, 1)
        self.assertEqual(never_subscribed_streams[0]["name"], "mit_stream_2")
        self.assertTrue(never_subscribed_streams[0]["is_web_public"])
        self.assertIsNone(never_subscribed_streams[0]["stream_weekly_traffic"])

    def test_nonsubscriber(self) -> None:
        """
        Even a non-subscriber to a public stream can query a stream's membership
        with get_subscribers.
        """
        # Create a stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.subscribe_via_post(self.user_profile, [stream_name])
        other_user = self.example_user("othello")

        # Fetch the subscriber list as a non-member.
        self.login_user(other_user)
        self.make_successful_subscriber_request(stream_name)

    def test_subscriber_private_stream(self) -> None:
        """
        A subscriber to a private stream can query that stream's membership.
        """
        stream_name = "Saxony"
        self.subscribe_via_post(self.user_profile, [stream_name], invite_only=True)
        self.make_successful_subscriber_request(stream_name)

        stream_id = get_stream(stream_name, self.user_profile.realm).id
        # Verify another user can't get the data.
        self.login("cordelia")
        result = self.client_get(f"/json/streams/{stream_id}/members")
        self.assert_json_error(result, "Invalid channel ID")

        # But an organization administrator can
        self.login("iago")
        result = self.client_get(f"/json/streams/{stream_id}/members")
        self.assert_json_success(result)

    def test_json_get_subscribers_stream_not_exist(self) -> None:
        """
        json_get_subscribers also returns the list of subscribers for a stream.
        """
        stream_id = 99999999
        result = self.client_get(f"/json/streams/{stream_id}/members")
        self.assert_json_error(result, "Invalid channel ID")

    def test_json_get_subscribers(self) -> None:
        """
        json_get_subscribers in zerver/views/streams.py
        also returns the list of subscribers for a stream, when requested.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]["name"]
        stream_id = get_stream(stream_name, self.user_profile.realm).id
        expected_subscribers = gather_subscriptions(self.user_profile, include_subscribers=True)[0][
            0
        ]["subscribers"]
        result = self.client_get(f"/json/streams/{stream_id}/members")
        result_dict = self.assert_json_success(result)
        self.assertIn("subscribers", result_dict)
        self.assertIsInstance(result_dict["subscribers"], list)
        subscribers: list[int] = []
        for subscriber in result_dict["subscribers"]:
            self.assertIsInstance(subscriber, int)
            subscribers.append(subscriber)
        self.assertEqual(set(subscribers), set(expected_subscribers))

    def test_json_get_subscribers_for_guest_user(self) -> None:
        """
        Guest users should have access to subscribers of web-public streams, even
        if they aren't subscribed or have never subscribed to that stream.
        """
        guest_user = self.example_user("polonius")
        never_subscribed = gather_subscriptions_helper(guest_user, True).never_subscribed

        # A guest user can only see never subscribed streams that are web-public.
        # For Polonius, the only web-public stream that he is not subscribed at
        # this point is Rome.
        self.assert_length(never_subscribed, 1)

        web_public_stream_id = never_subscribed[0]["stream_id"]
        result = self.client_get(f"/json/streams/{web_public_stream_id}/members")
        result_dict = self.assert_json_success(result)
        self.assertIn("subscribers", result_dict)
        self.assertIsInstance(result_dict["subscribers"], list)
        self.assertGreater(len(result_dict["subscribers"]), 0)

    def test_nonsubscriber_private_stream(self) -> None:
        """
        A non-subscriber non-realm-admin user to a private stream can't query that stream's membership.
        But unsubscribed realm admin users can query private stream's membership.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        stream_name = "NewStream"
        self.subscribe_via_post(self.user_profile, [stream_name], invite_only=True)
        user_profile = self.example_user("othello")

        # Try to fetch the subscriber list as a non-member & non-realm-admin-user.
        stream_id = get_stream(stream_name, user_profile.realm).id
        result = self.make_subscriber_request(stream_id, user=user_profile)
        self.assert_json_error(result, "Invalid channel ID")

        # Try to fetch the subscriber list as a non-member & realm-admin-user.
        self.login("iago")
        self.make_successful_subscriber_request(stream_name)
