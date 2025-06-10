from zerver.actions.streams import do_change_stream_group_based_setting, do_deactivate_stream
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.users import do_change_user_role
from zerver.lib.exceptions import JsonableError
from zerver.lib.streams import (
    access_stream_by_id,
    access_stream_by_name,
    bulk_can_access_stream_metadata_user_ids,
    can_access_stream_history,
    can_access_stream_metadata_user_ids,
    ensure_stream,
    user_has_content_access,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.types import UserGroupMembersData
from zerver.lib.user_groups import UserGroupMembershipDetails
from zerver.models import NamedUserGroup, Stream, UserProfile
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream
from zerver.models.users import active_non_guest_user_ids


class AccessStreamTest(ZulipTestCase):
    def test_access_stream(self) -> None:
        """
        A comprehensive security test for the access_stream_by_* API functions.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        hamlet = self.example_user("hamlet")

        stream_name = "new_private_stream"
        self.login_user(hamlet)
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        othello = self.example_user("othello")

        # Nobody can access a stream that doesn't exist
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(hamlet, 501232)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'invalid stream'"):
            access_stream_by_name(hamlet, "invalid stream")

        # Hamlet can access the private stream
        (stream_ret, sub_ret) = access_stream_by_id(hamlet, stream.id)
        self.assertEqual(stream.id, stream_ret.id)
        assert sub_ret is not None
        self.assertEqual(sub_ret.recipient.type_id, stream.id)
        (stream_ret2, sub_ret2) = access_stream_by_name(hamlet, stream.name)
        self.assertEqual(stream_ret.id, stream_ret2.id)
        self.assertEqual(sub_ret, sub_ret2)

        # Othello cannot access the private stream
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(othello, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(othello, stream.name)

        # Both Othello and Hamlet can access a public stream that only
        # Hamlet is subscribed to in this realm
        public_stream_name = "public_stream"
        self.subscribe_via_post(hamlet, [public_stream_name], invite_only=False)
        public_stream = get_stream(public_stream_name, hamlet.realm)
        access_stream_by_id(othello, public_stream.id)
        access_stream_by_name(othello, public_stream.name)
        access_stream_by_id(hamlet, public_stream.id)
        access_stream_by_name(hamlet, public_stream.name)

        # Archive channel to verify require_active_channel code path
        do_deactivate_stream(public_stream, acting_user=hamlet)
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(hamlet, public_stream.id, require_active_channel=True)
        access_stream_by_id(hamlet, public_stream.id, require_active_channel=False)

        # Nobody can access a public stream in another realm
        mit_realm = get_realm("zephyr")
        mit_stream = ensure_stream(mit_realm, "mit_stream", invite_only=False, acting_user=None)
        sipbtest = self.mit_user("sipbtest")
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(hamlet, mit_stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'mit_stream'"):
            access_stream_by_name(hamlet, mit_stream.name)
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(sipbtest, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(sipbtest, stream.name)

        # MIT realm users cannot access even public streams in their realm
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(sipbtest, mit_stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'mit_stream'"):
            access_stream_by_name(sipbtest, mit_stream.name)

        # But they can access streams they are subscribed to
        self.subscribe_via_post(sipbtest, [mit_stream.name], subdomain="zephyr")
        access_stream_by_id(sipbtest, mit_stream.id)
        access_stream_by_name(sipbtest, mit_stream.name)

    def test_access_stream_allow_metadata_access_flag(self) -> None:
        """
        A comprehensive security test for the access_stream_by_* API functions.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        hamlet = self.example_user("hamlet")

        stream_name = "new_private_stream"
        self.login_user(hamlet)
        self.subscribe_via_post(hamlet, [stream_name], invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        othello = self.example_user("othello")
        iago = self.example_user("iago")
        polonius = self.example_user("polonius")

        # Realm admin cannot access the private stream
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(iago, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(iago, stream.name)

        # Realm admins can access private stream if
        # require_content_access set to False
        access_stream_by_id(iago, stream.id, require_content_access=False)
        access_stream_by_name(iago, stream.name, require_content_access=False)

        # Normal unsubscribed user cannot access a private stream
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(othello, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(othello, stream.name)

        # Normal unsubscribed user cannot access a private stream with
        # require_content_access set to False
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(othello, stream.id, require_content_access=False)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(othello, stream.name, require_content_access=False)

        polonius_and_othello_group = check_add_user_group(
            othello.realm, "user_profile_group", [othello, polonius], acting_user=othello
        )
        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", is_system_group=True, realm=othello.realm
        )

        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            polonius_and_othello_group,
            acting_user=othello,
        )
        # Channel admins can access private stream if
        # require_content_access is set to False
        access_stream_by_id(othello, stream.id, require_content_access=False)
        access_stream_by_name(othello, stream.name, require_content_access=False)
        # Guest user who is a channel admin cannot access a stream via
        # groups if they are not subscribed to it.
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(polonius, stream.id, require_content_access=False)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(polonius, stream.name, require_content_access=False)
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            nobody_group,
            acting_user=othello,
        )

        do_change_stream_group_based_setting(
            stream,
            "can_add_subscribers_group",
            polonius_and_othello_group,
            acting_user=othello,
        )
        access_stream_by_id(othello, stream.id, require_content_access=False)
        access_stream_by_name(othello, stream.name, require_content_access=False)
        # Users in `can_add_subscribers_group` can access private
        # stream if require_content_access is set to True
        access_stream_by_id(othello, stream.id, require_content_access=True)
        access_stream_by_name(othello, stream.name, require_content_access=True)
        # Guest user who cannot access a stream via groups if they are
        # part of `can_add_subscribers_group` but not subscribed to it.
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(polonius, stream.id, require_content_access=False)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(polonius, stream.name, require_content_access=False)
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(polonius, stream.id, require_content_access=True)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(polonius, stream.name, require_content_access=True)

        do_change_stream_group_based_setting(
            stream,
            "can_add_subscribers_group",
            nobody_group,
            acting_user=othello,
        )

        do_change_stream_group_based_setting(
            stream,
            "can_subscribe_group",
            polonius_and_othello_group,
            acting_user=othello,
        )
        access_stream_by_id(othello, stream.id, require_content_access=False)
        access_stream_by_name(othello, stream.name, require_content_access=False)
        # Users in `can_subscribe_group` can access private
        # stream if require_content_access is set to True
        access_stream_by_id(othello, stream.id, require_content_access=True)
        access_stream_by_name(othello, stream.name, require_content_access=True)
        # Guest user who cannot access a stream via groups if they are
        # part of `can_subscribe_group` but not subscribed to it.
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(polonius, stream.id, require_content_access=False)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(polonius, stream.name, require_content_access=False)
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(polonius, stream.id, require_content_access=True)
        with self.assertRaisesRegex(JsonableError, "Invalid channel name 'new_private_stream'"):
            access_stream_by_name(polonius, stream.name, require_content_access=True)

    def test_stream_access_by_guest(self) -> None:
        guest_user_profile = self.example_user("polonius")
        self.login_user(guest_user_profile)
        stream_name = "public_stream_1"
        stream = self.make_stream(stream_name, guest_user_profile.realm, invite_only=False)

        # Guest user don't have access to unsubscribed public streams
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(guest_user_profile, stream.id)

        # Guest user have access to subscribed public streams
        self.subscribe(guest_user_profile, stream_name)
        (stream_ret, sub_ret) = access_stream_by_id(guest_user_profile, stream.id)
        assert sub_ret is not None
        self.assertEqual(stream.id, stream_ret.id)
        self.assertEqual(sub_ret.recipient.type_id, stream.id)

        stream_name = "private_stream_1"
        stream = self.make_stream(stream_name, guest_user_profile.realm, invite_only=True)
        # Obviously, a guest user doesn't have access to unsubscribed private streams either
        with self.assertRaisesRegex(JsonableError, "Invalid channel ID"):
            access_stream_by_id(guest_user_profile, stream.id)

        # Guest user have access to subscribed private streams
        self.subscribe(guest_user_profile, stream_name)
        (stream_ret, sub_ret) = access_stream_by_id(guest_user_profile, stream.id)
        assert sub_ret is not None
        self.assertEqual(stream.id, stream_ret.id)
        self.assertEqual(sub_ret.recipient.type_id, stream.id)

        stream_name = "web_public_stream"
        stream = self.make_stream(stream_name, guest_user_profile.realm, is_web_public=True)
        # Guest users have access to web-public streams even if they aren't subscribed.
        (stream_ret, sub_ret) = access_stream_by_id(guest_user_profile, stream.id)
        self.assertTrue(can_access_stream_history(guest_user_profile, stream))
        assert sub_ret is None
        self.assertEqual(stream.id, stream_ret.id)

    def test_has_content_access(self) -> None:
        guest_user = self.example_user("polonius")
        aaron = self.example_user("aaron")
        realm = guest_user.realm
        web_public_stream = self.make_stream("web_public_stream", realm=realm, is_web_public=True)
        private_stream = self.make_stream("private_stream", realm=realm, invite_only=True)
        public_stream = self.make_stream("public_stream", realm=realm, invite_only=False)

        # Even guest user should have access to web public channel.
        self.assertEqual(
            user_has_content_access(
                guest_user,
                web_public_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=False,
            ),
            True,
        )

        # User should have access to private channel if they are
        # subscribed to it
        self.assertEqual(
            user_has_content_access(
                aaron,
                private_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=True,
            ),
            True,
        )
        self.assertEqual(
            user_has_content_access(
                aaron,
                private_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=False,
            ),
            False,
        )

        # Non guest user should have access to public channel
        # regardless of their subscription to the channel.
        self.assertEqual(
            user_has_content_access(
                aaron,
                public_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=True,
            ),
            True,
        )
        self.assertEqual(
            user_has_content_access(
                aaron,
                public_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=False,
            ),
            True,
        )

        # Guest user should have access to public channel only if they
        # are subscribed to it.
        self.assertEqual(
            user_has_content_access(
                guest_user,
                public_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=False,
            ),
            False,
        )
        self.assertEqual(
            user_has_content_access(
                guest_user,
                public_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=True,
            ),
            True,
        )

        # User should be able to access private channel if they are
        # part of `can_add_subscribers_group` but not subscribed to the
        # channel.
        aaron_group_member_dict = UserGroupMembersData(
            direct_members=[aaron.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            private_stream,
            "can_add_subscribers_group",
            aaron_group_member_dict,
            acting_user=aaron,
        )
        self.assertEqual(
            user_has_content_access(
                aaron,
                private_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=False,
            ),
            True,
        )
        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            private_stream,
            "can_add_subscribers_group",
            nobody_group,
            acting_user=aaron,
        )

        # User should be able to access private channel if they are
        # part of `can_subscribe_group` but not subscribed to the
        # channel.
        do_change_stream_group_based_setting(
            private_stream,
            "can_subscribe_group",
            aaron_group_member_dict,
            acting_user=aaron,
        )
        self.assertEqual(
            user_has_content_access(
                aaron,
                private_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=False,
            ),
            True,
        )
        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            private_stream,
            "can_subscribe_group",
            nobody_group,
            acting_user=aaron,
        )

        # User should not be able to access private channel if they are
        # part of `can_administer_channel_group` but not subscribed to
        # the channel.
        do_change_stream_group_based_setting(
            private_stream,
            "can_administer_channel_group",
            aaron_group_member_dict,
            acting_user=aaron,
        )
        self.assertEqual(
            user_has_content_access(
                aaron,
                private_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=False,
            ),
            False,
        )
        self.assertEqual(
            user_has_content_access(
                aaron,
                private_stream,
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
                is_subscribed=True,
            ),
            True,
        )

    def test_can_access_stream_metadata_user_ids(self) -> None:
        aaron = self.example_user("aaron")
        cordelia = self.example_user("cordelia")
        guest_user = self.example_user("polonius")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        realm = aaron.realm
        public_stream = self.make_stream("public_stream", realm, invite_only=False)
        nobody_system_group = NamedUserGroup.objects.get(
            name="role:nobody", realm=realm, is_system_group=True
        )

        # Public stream with no subscribers.
        expected_public_user_ids = set(active_non_guest_user_ids(realm.id))
        self.assertCountEqual(
            can_access_stream_metadata_user_ids(public_stream), expected_public_user_ids
        )
        bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
            [public_stream]
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
        )

        # Public stream with 1 guest as a subscriber.
        self.subscribe(guest_user, "public_stream")
        expected_public_user_ids.add(guest_user.id)
        self.assertCountEqual(
            can_access_stream_metadata_user_ids(public_stream), expected_public_user_ids
        )
        bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
            [public_stream]
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
        )

        test_bot = self.create_test_bot("foo", desdemona)
        expected_public_user_ids.add(test_bot.id)
        private_stream = self.make_stream("private_stream", realm, invite_only=True)
        # Nobody is subscribed yet for the private stream, only admin
        # users will turn up for that stream. We will continue testing
        # the existing public stream for the bulk function here on.
        expected_private_user_ids = {iago.id, desdemona.id}
        self.assertCountEqual(
            can_access_stream_metadata_user_ids(private_stream), expected_private_user_ids
        )
        bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
            [public_stream, private_stream]
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
        )

        # Bot with admin privileges should also be part of the result.
        do_change_user_role(test_bot, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=desdemona)
        expected_private_user_ids.add(test_bot.id)
        self.assertCountEqual(
            can_access_stream_metadata_user_ids(private_stream), expected_private_user_ids
        )
        bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
            [public_stream, private_stream]
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
        )

        # Subscriber should also be part of the result.
        self.subscribe(aaron, "private_stream")
        expected_private_user_ids.add(aaron.id)
        self.assertCountEqual(
            can_access_stream_metadata_user_ids(private_stream), expected_private_user_ids
        )
        bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
            [public_stream, private_stream]
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
        )

        stream_permission_group_settings = set(Stream.stream_permission_group_settings.keys())
        stream_permission_group_settings_not_granting_metadata_access = (
            stream_permission_group_settings
            - set(Stream.stream_permission_group_settings_granting_metadata_access)
        )
        for setting_name in stream_permission_group_settings_not_granting_metadata_access:
            do_change_stream_group_based_setting(
                private_stream,
                setting_name,
                UserGroupMembersData(direct_members=[cordelia.id], direct_subgroups=[]),
                acting_user=cordelia,
            )
            with self.assert_database_query_count(4):
                private_stream_metadata_user_ids = can_access_stream_metadata_user_ids(
                    private_stream
                )
            self.assertCountEqual(private_stream_metadata_user_ids, expected_private_user_ids)
            with self.assert_database_query_count(6):
                bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
                    [public_stream, private_stream]
                )
            self.assertCountEqual(
                bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
            )
            self.assertCountEqual(
                bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
            )

        for setting_name in Stream.stream_permission_group_settings_granting_metadata_access:
            do_change_stream_group_based_setting(
                private_stream,
                setting_name,
                UserGroupMembersData(direct_members=[cordelia.id], direct_subgroups=[]),
                acting_user=cordelia,
            )
            expected_private_user_ids.add(cordelia.id)
            with self.assert_database_query_count(4):
                private_stream_metadata_user_ids = can_access_stream_metadata_user_ids(
                    private_stream
                )
            self.assertCountEqual(private_stream_metadata_user_ids, expected_private_user_ids)
            with self.assert_database_query_count(6):
                bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
                    [public_stream, private_stream]
                )
            self.assertCountEqual(
                bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
            )
            self.assertCountEqual(
                bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
            )

            do_change_stream_group_based_setting(
                private_stream, setting_name, nobody_system_group, acting_user=cordelia
            )
            expected_private_user_ids.remove(cordelia.id)
            bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
                [public_stream, private_stream]
            )
            self.assertCountEqual(
                can_access_stream_metadata_user_ids(private_stream), expected_private_user_ids
            )
            self.assertCountEqual(
                bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
            )
            self.assertCountEqual(
                bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
            )

        # Query count should not increase on fetching user ids for an
        # additional public stream.
        public_stream_2 = self.make_stream("public_stream_2", realm, invite_only=False)
        with self.assert_database_query_count(6):
            bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
                [public_stream, public_stream_2, private_stream]
            )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream_2.id],
            active_non_guest_user_ids(realm.id),
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
        )

        # Query count should not increase on fetching user ids for an
        # additional private stream.
        private_stream_2 = self.make_stream("private_stream_2", realm, invite_only=True)
        self.subscribe(aaron, "private_stream_2")
        with self.assert_database_query_count(6):
            bulk_access_stream_metadata_user_ids = bulk_can_access_stream_metadata_user_ids(
                [public_stream, public_stream_2, private_stream, private_stream_2]
            )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream.id], expected_public_user_ids
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[public_stream_2.id],
            active_non_guest_user_ids(realm.id),
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[private_stream.id], expected_private_user_ids
        )
        self.assertCountEqual(
            bulk_access_stream_metadata_user_ids[private_stream_2.id], expected_private_user_ids
        )
