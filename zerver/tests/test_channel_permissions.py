import orjson
from typing_extensions import override

from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_set_realm_property,
)
from zerver.actions.streams import do_change_stream_group_based_setting
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.users import do_change_user_role
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_subscription
from zerver.lib.types import UserGroupMembersData
from zerver.models import NamedUserGroup, Recipient, Stream, Subscription, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream


class ChannelSubscriptionPermissionTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.test_user = self.example_user("hamlet")

    def test_realm_settings_for_subscribing_other_users(self) -> None:
        """
        You can't subscribe other people to streams if you are a guest or your account is not old
        enough.
        """
        user_profile = self.example_user("cordelia")
        invitee_user_id = user_profile.id
        realm = user_profile.realm

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_add_subscribers_group", admins_group, acting_user=None
        )

        # User should be allowed to add subscribers when creating the
        # channel even if they don't have realm wide permission to
        # add other subscribers to a channel.
        do_change_user_role(self.test_user, UserProfile.ROLE_MODERATOR, acting_user=None)
        result = self.subscribe_via_post(
            self.test_user,
            ["stream1"],
            # Creator will be part of `can_administer_channel_group` by
            # default for a new channel. We set it to admin, so that we
            # can test for errors in the next piece of this test.
            {
                "principals": orjson.dumps([invitee_user_id]).decode(),
                "can_administer_channel_group": admins_group.id,
            },
            allow_fail=True,
        )
        self.assert_json_success(result)

        result = self.subscribe_via_post(
            self.test_user,
            ["stream1"],
            {"principals": orjson.dumps([self.example_user("aaron").id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_add_subscribers_group", nobody_group, acting_user=None
        )
        do_change_stream_group_based_setting(
            get_stream("stream1", realm),
            "can_add_subscribers_group",
            nobody_group,
            acting_user=user_profile,
        )
        # Admins have a special permission to administer every channel
        # they have access to. This also grants them access to add
        # subscribers.
        do_change_user_role(self.test_user, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        self.subscribe_via_post(
            self.test_user, ["stream1"], {"principals": orjson.dumps([invitee_user_id]).decode()}
        )

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_add_subscribers_group", moderators_group, acting_user=None
        )

        do_change_user_role(self.test_user, UserProfile.ROLE_MEMBER, acting_user=None)
        # Make sure that we are checking the permission with a full member,
        # as full member is the user just below moderator in the role hierarchy.
        self.assertFalse(self.test_user.is_provisional_member)
        # User will be able to add subscribers to a newly created
        # stream without any realm wide permissions. We create this
        # stream programmatically so that we can test for errors for an
        # existing stream.
        self.make_stream("stream2")
        result = self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        do_change_user_role(self.test_user, UserProfile.ROLE_MODERATOR, acting_user=None)
        self.subscribe_via_post(
            self.test_user, ["stream2"], {"principals": orjson.dumps([invitee_user_id]).decode()}
        )
        self.unsubscribe(user_profile, "stream2")

        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_add_subscribers_group", members_group, acting_user=None
        )
        do_change_user_role(self.test_user, UserProfile.ROLE_GUEST, acting_user=None)
        result = self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Not allowed for guest users")

        do_change_user_role(self.test_user, UserProfile.ROLE_MEMBER, acting_user=None)
        self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([self.test_user.id, invitee_user_id]).decode()},
        )
        self.unsubscribe(user_profile, "stream2")

        full_members_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_add_subscribers_group", full_members_group, acting_user=None
        )
        do_set_realm_property(realm, "waiting_period_threshold", 100000, acting_user=None)
        self.assertTrue(user_profile.is_provisional_member)
        result = self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        # Moderators, Admins and owners are always full members.
        self.assertTrue(user_profile.is_provisional_member)
        do_change_user_role(self.test_user, UserProfile.ROLE_MODERATOR, acting_user=None)
        self.assertFalse(self.test_user.is_provisional_member)
        do_change_user_role(self.test_user, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        self.assertFalse(self.test_user.is_provisional_member)
        do_change_user_role(self.test_user, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        self.assertFalse(self.test_user.is_provisional_member)

        do_set_realm_property(realm, "waiting_period_threshold", 0, acting_user=None)
        self.subscribe_via_post(
            self.test_user, ["stream2"], {"principals": orjson.dumps([invitee_user_id]).decode()}
        )
        self.unsubscribe(user_profile, "stream2")

        named_user_group = check_add_user_group(
            realm, "named_user_group", [self.test_user], acting_user=self.test_user
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_add_subscribers_group",
            named_user_group,
            acting_user=None,
        )
        self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
        )
        self.unsubscribe(user_profile, "stream2")
        anonymous_group = self.create_or_update_anonymous_group_for_setting([self.test_user], [])

        do_change_realm_permission_group_setting(
            realm,
            "can_add_subscribers_group",
            anonymous_group,
            acting_user=None,
        )
        self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
        )
        self.unsubscribe(user_profile, "stream2")

    def test_stream_settings_for_subscribing_other_users(self) -> None:
        user_profile = self.example_user("cordelia")
        invitee_user_id = user_profile.id
        realm = user_profile.realm

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_add_subscribers_group", nobody_group, acting_user=None
        )

        # User will be able to add subscribers to a newly created
        # stream without any realm wide permissions. We create this
        # stream programmatically so that we can test for errors for an
        # existing stream.
        do_change_stream_group_based_setting(
            self.make_stream("stream1"),
            "can_add_subscribers_group",
            nobody_group,
            acting_user=user_profile,
        )
        result = self.subscribe_via_post(
            self.test_user,
            ["stream1"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        # Admins have a special permission to administer every channel
        # they have access to. This also grants them access to add
        # subscribers.
        do_change_user_role(self.test_user, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.subscribe_via_post(
            self.test_user, ["stream1"], {"principals": orjson.dumps([invitee_user_id]).decode()}
        )
        self.assert_json_success(result)

        do_change_user_role(self.test_user, UserProfile.ROLE_MEMBER, acting_user=None)
        # Make sure that we are checking the permission with a full member,
        # as full member is the user just below moderator in the role hierarchy.
        self.assertFalse(self.test_user.is_provisional_member)

        # User will be able to add subscribers to a newly created
        # stream without any realm wide permissions. We create this
        # stream programmatically so that we can test for errors for an
        # existing stream.
        stream2 = self.make_stream("stream2")
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            stream2, "can_add_subscribers_group", moderators_group, acting_user=user_profile
        )
        result = self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        do_change_user_role(self.test_user, UserProfile.ROLE_MODERATOR, acting_user=None)
        self.subscribe_via_post(
            self.test_user, ["stream2"], {"principals": orjson.dumps([invitee_user_id]).decode()}
        )
        self.unsubscribe(user_profile, "stream2")

        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            stream2, "can_add_subscribers_group", members_group, acting_user=user_profile
        )
        do_change_user_role(self.test_user, UserProfile.ROLE_GUEST, acting_user=None)
        result = self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Not allowed for guest users")

        do_change_user_role(self.test_user, UserProfile.ROLE_MEMBER, acting_user=None)
        self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([self.test_user.id, invitee_user_id]).decode()},
        )
        self.unsubscribe(user_profile, "stream2")

        # User should be able to subscribe other users if they have
        # permissions to administer the channel.
        do_change_stream_group_based_setting(
            stream2, "can_add_subscribers_group", nobody_group, acting_user=user_profile
        )
        do_change_stream_group_based_setting(
            stream2, "can_administer_channel_group", members_group, acting_user=user_profile
        )
        self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([self.test_user.id, invitee_user_id]).decode()},
        )
        self.unsubscribe(user_profile, "stream2")
        do_change_stream_group_based_setting(
            stream2, "can_administer_channel_group", nobody_group, acting_user=user_profile
        )

        full_members_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            stream2, "can_add_subscribers_group", full_members_group, acting_user=user_profile
        )
        do_set_realm_property(realm, "waiting_period_threshold", 100000, acting_user=None)
        result = self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        do_set_realm_property(realm, "waiting_period_threshold", 0, acting_user=None)
        self.subscribe_via_post(
            self.test_user, ["stream2"], {"principals": orjson.dumps([invitee_user_id]).decode()}
        )
        self.unsubscribe(user_profile, "stream2")

        named_user_group = check_add_user_group(
            realm, "named_user_group", [self.test_user], acting_user=self.test_user
        )
        do_change_stream_group_based_setting(
            stream2,
            "can_add_subscribers_group",
            named_user_group,
            acting_user=user_profile,
        )
        self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
        )
        self.unsubscribe(user_profile, "stream2")
        anonymous_group_member_dict = UserGroupMembersData(
            direct_members=[self.test_user.id], direct_subgroups=[]
        )

        do_change_stream_group_based_setting(
            stream2,
            "can_add_subscribers_group",
            anonymous_group_member_dict,
            acting_user=user_profile,
        )
        self.subscribe_via_post(
            self.test_user,
            ["stream2"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
        )
        self.unsubscribe(user_profile, "stream2")

        private_stream = self.make_stream("private_stream", invite_only=True)
        do_change_stream_group_based_setting(
            private_stream, "can_add_subscribers_group", members_group, acting_user=user_profile
        )
        result = self.subscribe_via_post(
            self.test_user,
            ["private_stream"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
        )
        self.assert_json_success(result)
        do_change_stream_group_based_setting(
            private_stream, "can_add_subscribers_group", nobody_group, acting_user=user_profile
        )
        self.unsubscribe(user_profile, "private_stream")

        do_change_stream_group_based_setting(
            private_stream,
            "can_administer_channel_group",
            members_group,
            acting_user=user_profile,
        )
        result = self.subscribe_via_post(
            self.test_user,
            ["private_stream"],
            {"principals": orjson.dumps([invitee_user_id]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "Unable to access channel (private_stream).")

    def test_stream_settings_for_subscribing(self) -> None:
        realm = get_realm("zulip")

        stream = self.make_stream("public_stream")

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )

        def check_user_can_subscribe(user: UserProfile, error_msg: str | None = None) -> None:
            result = self.subscribe_via_post(
                user,
                [stream.name],
                allow_fail=error_msg is not None,
            )
            if error_msg:
                self.assert_json_error(result, error_msg)
                return

            self.assertTrue(
                Subscription.objects.filter(
                    recipient__type=Recipient.STREAM,
                    recipient__type_id=stream.id,
                    user_profile=user,
                ).exists()
            )
            # Unsubscribe user again for testing next case.
            self.unsubscribe(user, stream.name)

        desdemona = self.example_user("desdemona")
        shiva = self.example_user("shiva")
        hamlet = self.example_user("hamlet")
        polonius = self.example_user("polonius")
        othello = self.example_user("othello")

        do_change_realm_permission_group_setting(
            realm, "can_add_subscribers_group", nobody_group, acting_user=othello
        )
        do_change_stream_group_based_setting(
            stream, "can_add_subscribers_group", nobody_group, acting_user=othello
        )
        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", nobody_group, acting_user=othello
        )

        check_user_can_subscribe(desdemona)
        check_user_can_subscribe(shiva)
        check_user_can_subscribe(hamlet)
        check_user_can_subscribe(othello)
        check_user_can_subscribe(polonius, "Not allowed for guest users")

        setting_group_member_dict = UserGroupMembersData(
            direct_members=[polonius.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", setting_group_member_dict, acting_user=othello
        )

        check_user_can_subscribe(polonius, "Not allowed for guest users")

        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", nobody_group, acting_user=othello
        )
        do_change_stream_group_based_setting(
            stream, "can_add_subscribers_group", setting_group_member_dict, acting_user=othello
        )

        check_user_can_subscribe(polonius, "Not allowed for guest users")

        do_change_stream_group_based_setting(
            stream, "can_add_subscribers_group", nobody_group, acting_user=othello
        )
        do_change_stream_group_based_setting(
            stream, "can_administer_channel_group", setting_group_member_dict, acting_user=othello
        )

        check_user_can_subscribe(polonius, "Not allowed for guest users")

        stream = self.subscribe(self.example_user("iago"), "private_stream", invite_only=True)

        check_user_can_subscribe(desdemona, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(shiva, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(hamlet, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(othello, f"Unable to access channel ({stream.name}).")

        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", owners_group, acting_user=othello
        )

        check_user_can_subscribe(shiva, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(hamlet, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(othello, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(desdemona)

        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)
        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", hamletcharacters_group, acting_user=othello
        )
        check_user_can_subscribe(shiva, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(desdemona, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(othello, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(hamlet)

        setting_group_member_dict = UserGroupMembersData(
            direct_members=[othello.id], direct_subgroups=[owners_group.id]
        )
        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", setting_group_member_dict, acting_user=othello
        )
        check_user_can_subscribe(shiva, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(hamlet, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(othello)
        check_user_can_subscribe(desdemona)

        # Users can also subscribe if they are allowed to subscribe other users.
        do_change_stream_group_based_setting(
            stream, "can_subscribe_group", nobody_group, acting_user=othello
        )
        do_change_stream_group_based_setting(
            stream, "can_add_subscribers_group", setting_group_member_dict, acting_user=othello
        )
        check_user_can_subscribe(shiva, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(hamlet, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(othello)
        check_user_can_subscribe(desdemona)

        # Users cannot subscribe if they belong to can_administer_channel_group but
        # do not belong to any of can_subscribe_group and can_add_subscribers_group.
        do_change_stream_group_based_setting(
            stream, "can_add_subscribers_group", nobody_group, acting_user=othello
        )
        do_change_stream_group_based_setting(
            stream, "can_administer_channel_group", setting_group_member_dict, acting_user=othello
        )
        check_user_can_subscribe(shiva, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(hamlet, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(othello, f"Unable to access channel ({stream.name}).")
        check_user_can_subscribe(desdemona, f"Unable to access channel ({stream.name}).")

    def test_can_remove_subscribers_group(self) -> None:
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        leadership_group = check_add_user_group(
            realm,
            "leadership",
            [iago, self.example_user("shiva")],
            acting_user=iago,
        )
        hamlet = self.example_user("hamlet")
        managers_group = check_add_user_group(realm, "managers", [hamlet], acting_user=hamlet)
        add_subgroups_to_user_group(managers_group, [leadership_group], acting_user=None)
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        shiva = self.example_user("shiva")

        public_stream = self.make_stream("public_stream")

        def check_unsubscribing_user(
            user: UserProfile,
            can_remove_subscribers_group: NamedUserGroup | UserGroupMembersData,
            expect_fail: bool = False,
            stream_list: list[Stream] | None = None,
            skip_changing_group_setting: bool = False,
        ) -> None:
            self.login_user(user)
            if stream_list is None:
                stream_list = [public_stream]
            for stream in stream_list:
                self.subscribe(cordelia, stream.name)
                if not skip_changing_group_setting:
                    do_change_stream_group_based_setting(
                        stream,
                        "can_remove_subscribers_group",
                        can_remove_subscribers_group,
                        acting_user=user,
                    )
            stream_name_list = [stream.name for stream in stream_list]
            result = self.client_delete(
                "/json/users/me/subscriptions",
                {
                    "subscriptions": orjson.dumps(stream_name_list).decode(),
                    "principals": orjson.dumps([cordelia.id]).decode(),
                },
            )
            if expect_fail:
                self.assert_json_error(result, "Insufficient permission")
                return

            json = self.assert_json_success(result)
            self.assert_length(json["removed"], len(stream_name_list))
            self.assert_length(json["not_removed"], 0)

        check_unsubscribing_user(
            self.example_user("hamlet"),
            leadership_group,
            expect_fail=True,
            stream_list=[public_stream],
        )
        check_unsubscribing_user(iago, leadership_group, stream_list=[public_stream])
        # Owners can unsubscribe others when they are not a member of
        # the allowed group since owners have the permission to
        # administer all channels.
        check_unsubscribing_user(
            self.example_user("desdemona"), leadership_group, stream_list=[public_stream]
        )

        check_unsubscribing_user(
            othello,
            managers_group,
            expect_fail=True,
            stream_list=[public_stream],
        )
        check_unsubscribing_user(shiva, managers_group, stream_list=[public_stream])
        check_unsubscribing_user(hamlet, managers_group, stream_list=[public_stream])

        private_stream = self.make_stream("private_stream", invite_only=True)
        self.subscribe(self.example_user("hamlet"), private_stream.name)
        # Users are not allowed to unsubscribe others from streams they
        # don't have metadata access to even if they are a member of the
        # allowed group. In this case, a non-admin who is not subscribed
        # to the channel does not have metadata access to the channel.
        check_unsubscribing_user(
            shiva,
            leadership_group,
            expect_fail=True,
            stream_list=[private_stream],
        )
        check_unsubscribing_user(iago, leadership_group, stream_list=[private_stream])
        # Users are allowed to unsubscribe others from private streams
        # they have access to if they are a member of the allowed
        # group. In this case, a user with the role `owner` is
        # subscribed to the relevant channel.
        check_unsubscribing_user(
            self.example_user("desdemona"), leadership_group, stream_list=[private_stream]
        )
        self.subscribe(shiva, private_stream.name)
        check_unsubscribing_user(shiva, leadership_group, stream_list=[private_stream])

        # Test changing setting to anonymous group.
        setting_group_member_dict = UserGroupMembersData(
            direct_members=[hamlet.id],
            direct_subgroups=[leadership_group.id],
        )
        check_unsubscribing_user(
            othello,
            setting_group_member_dict,
            expect_fail=True,
            stream_list=[private_stream],
        )
        check_unsubscribing_user(hamlet, setting_group_member_dict, stream_list=[private_stream])
        check_unsubscribing_user(iago, setting_group_member_dict, stream_list=[private_stream])
        check_unsubscribing_user(shiva, setting_group_member_dict, stream_list=[private_stream])

        # Owners can unsubscribe others when they are not a member of
        # the allowed group since admins have the permission to
        # administer all channels.
        setting_group_member_dict = UserGroupMembersData(
            direct_members=[hamlet.id],
            direct_subgroups=[],
        )
        check_unsubscribing_user(
            self.example_user("desdemona"), setting_group_member_dict, stream_list=[private_stream]
        )
        check_unsubscribing_user(iago, setting_group_member_dict, stream_list=[private_stream])

        # A user who is part of can_administer_channel_group should be
        # able to unsubscribe other users even if that user is not part
        # of can_remove_subscribers_group. And even if that user is not
        # subscribed to the channel in question.
        with self.assertRaises(Subscription.DoesNotExist):
            get_subscription(private_stream.name, othello)
        check_unsubscribing_user(othello, setting_group_member_dict, expect_fail=True)
        othello_group_member_dict = UserGroupMembersData(
            direct_members=[othello.id], direct_subgroups=[]
        )
        private_stream_2 = self.make_stream("private_stream_2")
        do_change_stream_group_based_setting(
            private_stream,
            "can_administer_channel_group",
            othello_group_member_dict,
            acting_user=othello,
        )
        # If the user can only administer one of the channels, the test
        # should fail.
        check_unsubscribing_user(
            othello,
            setting_group_member_dict,
            expect_fail=True,
            stream_list=[private_stream, private_stream_2],
        )
        # User can administer both channels now.
        do_change_stream_group_based_setting(
            private_stream_2,
            "can_administer_channel_group",
            othello_group_member_dict,
            acting_user=othello,
        )
        check_unsubscribing_user(
            othello, setting_group_member_dict, stream_list=[private_stream, private_stream_2]
        )

        shiva_group_member_dict = UserGroupMembersData(
            direct_members=[shiva.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            private_stream,
            "can_remove_subscribers_group",
            shiva_group_member_dict,
            acting_user=shiva,
        )
        self.subscribe(shiva, private_stream.name)
        self.subscribe(shiva, private_stream_2.name)
        # If the user can is present in the remove subscribers group of
        # only one of the channels, the test should fail.
        check_unsubscribing_user(
            shiva,
            setting_group_member_dict,
            expect_fail=True,
            stream_list=[private_stream, private_stream_2],
            skip_changing_group_setting=True,
        )
        do_change_stream_group_based_setting(
            private_stream_2,
            "can_remove_subscribers_group",
            shiva_group_member_dict,
            acting_user=shiva,
        )
        check_unsubscribing_user(
            shiva,
            setting_group_member_dict,
            stream_list=[private_stream, private_stream_2],
            skip_changing_group_setting=True,
        )
