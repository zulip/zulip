import orjson
from typing_extensions import override

from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_set_realm_property,
)
from zerver.actions.streams import do_change_stream_group_based_setting, do_deactivate_stream
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.users import do_change_user_role
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_subscription
from zerver.lib.types import UserGroupMembersData
from zerver.lib.user_groups import get_group_setting_value_for_api
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

    def test_change_stream_message_retention_days_requires_realm_owner(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        realm = user_profile.realm
        stream = self.subscribe(user_profile, "stream_name1")

        result = self.client_patch(
            f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(2).decode()}
        )
        self.assert_json_error(result, "Must be an organization owner")

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        result = self.client_patch(
            f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(2).decode()}
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.message_retention_days, 2)

    def do_test_channel_administering_permission(
        self, stream: Stream, property_name: str, new_value: str | int | bool
    ) -> None:
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        shiva = self.example_user("shiva")
        hamlet = self.example_user("hamlet")
        prospero = self.example_user("prospero")
        polonius = self.example_user("polonius")

        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )

        api_parameter_name_dict = dict(
            name="new_name",
            deactivated="is_archived",
            invite_only="is_private",
        )
        api_parameter_name = property_name
        if property_name in api_parameter_name_dict:
            api_parameter_name = api_parameter_name_dict[property_name]

        data = {}
        if property_name in Stream.stream_permission_group_settings:
            data[api_parameter_name] = orjson.dumps({"new": new_value}).decode()
        elif not isinstance(new_value, str):
            data[api_parameter_name] = orjson.dumps(new_value).decode()
        else:
            data[api_parameter_name] = new_value

        default_error_msg = "You do not have permission to administer this channel."

        def check_channel_property_update(
            user: UserProfile, allow_fail: bool = False, error_msg: str = default_error_msg
        ) -> None:
            old_value = getattr(stream, property_name)
            if property_name in Stream.stream_permission_group_settings:
                if not hasattr(old_value, "named_user_group"):
                    old_value = get_group_setting_value_for_api(old_value)
                else:
                    old_value = old_value.named_user_group

            result = self.api_patch(user, f"/api/v1/streams/{stream.id}", info=data)

            if allow_fail:
                self.assert_json_error(result, error_msg)
                return

            self.assert_json_success(result)
            stream.refresh_from_db()
            if property_name in Stream.stream_permission_group_settings:
                self.assertEqual(getattr(stream, property_name + "_id"), new_value)
            else:
                self.assertEqual(getattr(stream, property_name), new_value)

            # Reset to original value
            if property_name in Stream.stream_permission_group_settings:
                do_change_stream_group_based_setting(
                    stream, property_name, old_value, acting_user=iago
                )
            else:
                setattr(stream, property_name, old_value)
                stream.save(update_fields=[property_name])

            # Reset history_public_to_subscribers field when stream
            # is changed from private to public.
            if not stream.invite_only and not stream.history_public_to_subscribers:
                stream.history_public_to_subscribers = True
                stream.save(update_fields=["history_public_to_subscribers"])

        do_change_stream_group_based_setting(
            stream, "can_administer_channel_group", nobody_group, acting_user=iago
        )
        check_channel_property_update(shiva, allow_fail=True)
        # Admins can always administer a channel.
        check_channel_property_update(iago)

        do_change_stream_group_based_setting(
            stream, "can_administer_channel_group", moderators_group, acting_user=iago
        )
        check_channel_property_update(hamlet, allow_fail=True)
        check_channel_property_update(shiva)

        if property_name == "is_web_public" and new_value is True:
            # Members cannot create web-public channels, so
            # we do not check permission for further cases.
            return

        # Check when administering permission is set to a user-defined group.
        do_change_stream_group_based_setting(
            stream, "can_administer_channel_group", hamletcharacters_group, acting_user=iago
        )

        check_channel_property_update(shiva, allow_fail=True)
        check_channel_property_update(hamlet)

        # Check when administering permission is set to an anonymous groups.
        anonymous_group_dict = UserGroupMembersData(
            direct_members=[prospero.id, polonius.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            stream, "can_administer_channel_group", anonymous_group_dict, acting_user=iago
        )
        check_channel_property_update(hamlet, allow_fail=True)
        check_channel_property_update(shiva, allow_fail=True)
        check_channel_property_update(prospero)

        # Check guests cannot update property even when they belong
        # to "can_administer_channel_group".
        check_channel_property_update(polonius, allow_fail=True, error_msg="Invalid channel ID")
        self.subscribe(polonius, stream.name)
        check_channel_property_update(polonius, allow_fail=True)
        self.unsubscribe(polonius, stream.name)

        # If stream is private, test which permissions require having
        # content access to the channel. We do not test this for
        # public streams since all non-guest users have content
        # access to them.
        if stream.invite_only:
            # Unsubscribe user from private stream to test gaining
            # content access from group settings.
            self.unsubscribe(iago, stream.name)
            self.unsubscribe(shiva, stream.name)
            self.unsubscribe(hamlet, stream.name)
            do_change_stream_group_based_setting(
                stream, "can_administer_channel_group", members_group, acting_user=iago
            )

            if (
                property_name
                not in Stream.stream_permission_group_settings_requiring_content_access
                and property_name != "invite_only"
            ):
                # Users without content access can modify properties not in
                # stream_permission_group_settings_requiring_content_access
                # can change privacy of non-private streams, and can archive
                # or unarchive them.
                check_channel_property_update(iago)
                check_channel_property_update(shiva)
                check_channel_property_update(hamlet)
            else:
                error_msg = "Channel content access is required."
                # Even realm and channel admins need content access to a private
                # channel for changing its privacy and to update the permissions
                # in stream_permission_group_settings_requiring_content_access.
                check_channel_property_update(iago, allow_fail=True, error_msg=error_msg)
                check_channel_property_update(shiva, allow_fail=True, error_msg=error_msg)
                check_channel_property_update(hamlet, allow_fail=True, error_msg=error_msg)

                do_change_stream_group_based_setting(
                    stream, "can_add_subscribers_group", moderators_group, acting_user=iago
                )
                check_channel_property_update(hamlet, allow_fail=True, error_msg=error_msg)
                check_channel_property_update(iago)
                check_channel_property_update(shiva)

                do_change_stream_group_based_setting(
                    stream, "can_subscribe_group", hamletcharacters_group, acting_user=iago
                )
                check_channel_property_update(hamlet)

                # Reset the setting values to "Nobody" group.
                do_change_stream_group_based_setting(
                    stream, "can_add_subscribers_group", nobody_group, acting_user=iago
                )
                do_change_stream_group_based_setting(
                    stream, "can_subscribe_group", nobody_group, acting_user=iago
                )

            self.subscribe(iago, stream.name)
            self.subscribe(shiva, stream.name)
            self.subscribe(hamlet, stream.name)

    def test_channel_administering_permissions(self) -> None:
        """
        This test is only for checking channel administer permissions
        while updating different channel properties. Other things
        while updating these properties are tested separately.
        """
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        public_stream = self.make_stream("test stream")

        private_stream = self.make_stream("private_stream", invite_only=True)
        self.subscribe(iago, private_stream.name)
        self.subscribe(self.example_user("shiva"), private_stream.name)
        self.subscribe(self.example_user("hamlet"), private_stream.name)
        self.subscribe(self.example_user("prospero"), private_stream.name)

        channel_folder = check_add_channel_folder(realm, "Frontend", "", acting_user=iago)
        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)

        for stream in [public_stream, private_stream]:
            self.do_test_channel_administering_permission(stream, "name", "Renamed stream")
            self.do_test_channel_administering_permission(
                stream, "description", "Edited stream description"
            )
            self.do_test_channel_administering_permission(stream, "folder_id", channel_folder.id)

            for setting_name in Stream.stream_permission_group_settings:
                self.do_test_channel_administering_permission(
                    stream, setting_name, hamletcharacters_group.id
                )

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_create_web_public_channel_group", moderators_group, acting_user=None
        )

        # Test making a public stream private with protected history.
        self.do_test_channel_administering_permission(public_stream, "invite_only", True)

        # Test making a public stream web-public.
        self.do_test_channel_administering_permission(public_stream, "is_web_public", True)

        # Test making a private stream with protected history public.
        self.do_test_channel_administering_permission(private_stream, "invite_only", False)

        for stream in [public_stream, private_stream]:
            do_deactivate_stream(stream, acting_user=None)
            self.do_test_channel_administering_permission(stream, "deactivated", False)
