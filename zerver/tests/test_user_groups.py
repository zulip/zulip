from datetime import timedelta
from typing import Optional

import orjson
from django.utils.timezone import now as timezone_now

from zerver.lib.actions import do_set_realm_property, ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_usermessage
from zerver.lib.user_groups import (
    create_user_group,
    get_direct_memberships_of_users,
    get_direct_user_groups,
    get_recursive_group_members,
    get_recursive_membership_groups,
    get_recursive_subgroups,
    user_groups_in_realm_serialized,
)
from zerver.models import (
    GroupGroupMembership,
    Realm,
    UserGroup,
    UserGroupMembership,
    UserProfile,
    get_realm,
)


class UserGroupTestCase(ZulipTestCase):
    def create_user_group_for_test(
        self, group_name: str, realm: Realm = get_realm("zulip")
    ) -> UserGroup:
        members = [self.example_user("othello")]
        return create_user_group(group_name, members, realm)

    def test_user_groups_in_realm_serialized(self) -> None:
        realm = get_realm("zulip")
        user_group = UserGroup.objects.first()
        assert user_group is not None
        membership = UserGroupMembership.objects.filter(user_group=user_group)
        membership = membership.values_list("user_profile_id", flat=True)
        empty_user_group = create_user_group("newgroup", [], realm)

        user_groups = user_groups_in_realm_serialized(realm)
        self.assert_length(user_groups, 2)
        self.assertEqual(user_groups[0]["id"], user_group.id)
        self.assertEqual(user_groups[0]["name"], "hamletcharacters")
        self.assertEqual(user_groups[0]["description"], "Characters of Hamlet")
        self.assertEqual(set(user_groups[0]["members"]), set(membership))

        self.assertEqual(user_groups[1]["id"], empty_user_group.id)
        self.assertEqual(user_groups[1]["name"], "newgroup")
        self.assertEqual(user_groups[1]["description"], "")
        self.assertEqual(user_groups[1]["members"], [])

    def test_get_direct_user_groups(self) -> None:
        othello = self.example_user("othello")
        self.create_user_group_for_test("support")
        user_groups = get_direct_user_groups(othello)
        self.assert_length(user_groups, 1)
        self.assertEqual(user_groups[0].name, "support")

    def test_recursive_queries_for_user_groups(self) -> None:
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        shiva = self.example_user("shiva")

        leadership_group = UserGroup.objects.create(realm=realm, name="Leadership")
        UserGroupMembership.objects.create(user_profile=desdemona, user_group=leadership_group)

        staff_group = UserGroup.objects.create(realm=realm, name="Staff")
        UserGroupMembership.objects.create(user_profile=iago, user_group=staff_group)
        GroupGroupMembership.objects.create(supergroup=staff_group, subgroup=leadership_group)

        everyone_group = UserGroup.objects.create(realm=realm, name="Everyone")
        UserGroupMembership.objects.create(user_profile=shiva, user_group=everyone_group)
        GroupGroupMembership.objects.create(supergroup=everyone_group, subgroup=staff_group)

        self.assertCountEqual(list(get_recursive_subgroups(leadership_group)), [leadership_group])
        self.assertCountEqual(
            list(get_recursive_subgroups(staff_group)), [leadership_group, staff_group]
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(everyone_group)),
            [leadership_group, staff_group, everyone_group],
        )

        self.assertCountEqual(list(get_recursive_group_members(leadership_group)), [desdemona])
        self.assertCountEqual(list(get_recursive_group_members(staff_group)), [desdemona, iago])
        self.assertCountEqual(
            list(get_recursive_group_members(everyone_group)), [desdemona, iago, shiva]
        )

        self.assertCountEqual(
            list(get_recursive_membership_groups(desdemona)),
            [leadership_group, staff_group, everyone_group],
        )
        self.assertCountEqual(
            list(get_recursive_membership_groups(iago)), [staff_group, everyone_group]
        )
        self.assertCountEqual(list(get_recursive_membership_groups(shiva)), [everyone_group])


class UserGroupAPITestCase(UserGroupTestCase):
    def test_user_group_create(self) -> None:
        hamlet = self.example_user("hamlet")

        # Test success
        self.login("hamlet")
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        self.assert_length(UserGroup.objects.filter(realm=hamlet.realm), 2)

        # Test invalid member error
        params = {
            "name": "backend",
            "members": orjson.dumps([1111]).decode(),
            "description": "Backend team",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Invalid user ID: 1111")
        self.assert_length(UserGroup.objects.filter(realm=hamlet.realm), 2)

        # Test we cannot create group with same name again
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group 'support' already exists.")
        self.assert_length(UserGroup.objects.filter(realm=hamlet.realm), 2)

    def test_user_group_get(self) -> None:
        # Test success
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        result = self.client_get("/json/user_groups")
        self.assert_json_success(result)
        self.assert_length(
            result.json()["user_groups"], UserGroup.objects.filter(realm=user_profile.realm).count()
        )

    def test_can_edit_user_groups(self) -> None:
        def validation_func(user_profile: UserProfile) -> bool:
            user_profile.refresh_from_db()
            return user_profile.can_edit_user_groups()

        self.check_has_permission_policies("user_group_edit_policy", validation_func)

    def test_user_group_update(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        self.client_post("/json/user_groups/create", info=params)
        user_group = UserGroup.objects.get(name="support")
        # Test success
        params = {
            "name": "help",
            "description": "Troubleshooting team",
        }
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_success(result)

        # Test when new data is not supplied.
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info={})
        self.assert_json_error(result, "No new data supplied")

        # Test when invalid user group is supplied
        params = {"name": "help"}
        result = self.client_patch("/json/user_groups/1111", info=params)
        self.assert_json_error(result, "Invalid user group")

    def test_user_group_update_to_already_existing_name(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        realm = get_realm("zulip")
        support_user_group = create_user_group("support", [hamlet], realm)
        marketing_user_group = create_user_group("marketing", [hamlet], realm)

        params = {
            "name": marketing_user_group.name,
        }
        result = self.client_patch(f"/json/user_groups/{support_user_group.id}", info=params)
        self.assert_json_error(result, f"User group '{marketing_user_group.name}' already exists.")

    def test_user_group_delete(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        self.client_post("/json/user_groups/create", info=params)
        user_group = UserGroup.objects.get(name="support")
        # Test success
        self.assertEqual(UserGroup.objects.filter(realm=hamlet.realm).count(), 2)
        self.assertEqual(UserGroupMembership.objects.count(), 3)
        result = self.client_delete(f"/json/user_groups/{user_group.id}")
        self.assert_json_success(result)
        self.assertEqual(UserGroup.objects.filter(realm=hamlet.realm).count(), 1)
        self.assertEqual(UserGroupMembership.objects.count(), 2)
        # Test when invalid user group is supplied
        result = self.client_delete("/json/user_groups/1111")
        self.assert_json_error(result, "Invalid user group")

    def test_update_members_of_user_group(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        self.client_post("/json/user_groups/create", info=params)
        user_group = UserGroup.objects.get(name="support")
        # Test add members
        self.assertEqual(UserGroupMembership.objects.filter(user_group=user_group).count(), 1)

        othello = self.example_user("othello")
        add = [othello.id]
        params = {"add": orjson.dumps(add).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assertEqual(UserGroupMembership.objects.filter(user_group=user_group).count(), 2)
        members = get_direct_memberships_of_users(user_group, [hamlet, othello])
        self.assert_length(members, 2)

        # Test adding a member already there.
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_error(result, f"User {othello.id} is already a member of this group")
        self.assertEqual(UserGroupMembership.objects.filter(user_group=user_group).count(), 2)
        members = get_direct_memberships_of_users(user_group, [hamlet, othello])
        self.assert_length(members, 2)

        aaron = self.example_user("aaron")

        # For normal testing we again log in with hamlet
        self.logout()
        self.login_user(hamlet)
        # Test remove members
        params = {"delete": orjson.dumps([othello.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assertEqual(UserGroupMembership.objects.filter(user_group=user_group).count(), 1)
        members = get_direct_memberships_of_users(user_group, [hamlet, othello, aaron])
        self.assert_length(members, 1)

        # Test remove a member that's already removed
        params = {"delete": orjson.dumps([othello.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_error(result, f"There is no member '{othello.id}' in this user group")
        self.assertEqual(UserGroupMembership.objects.filter(user_group=user_group).count(), 1)
        members = get_direct_memberships_of_users(user_group, [hamlet, othello, aaron])
        self.assert_length(members, 1)

        # Test when nothing is provided
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info={})
        msg = 'Nothing to do. Specify at least one of "add" or "delete".'
        self.assert_json_error(result, msg)

    def test_mentions(self) -> None:
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        zoe = self.example_user("ZOE")

        realm = cordelia.realm

        group_name = "support"
        stream_name = "Dev help"

        content_with_group_mention = "hey @*support* can you help us with this?"

        ensure_stream(realm, stream_name, acting_user=None)

        all_users = {cordelia, hamlet, othello, zoe}
        support_team = {hamlet, zoe}
        sender = cordelia
        other_users = all_users - support_team

        for user in all_users:
            self.subscribe(user, stream_name)

        create_user_group(
            name=group_name,
            members=list(support_team),
            realm=realm,
        )

        payload = dict(
            type="stream",
            to=stream_name,
            client="test suite",
            topic="whatever",
            content=content_with_group_mention,
        )

        result = self.api_post(sender, "/json/messages", payload)

        self.assert_json_success(result)

        for user in support_team:
            um = most_recent_usermessage(user)
            self.assertTrue(um.flags.mentioned)

        for user in other_users:
            um = most_recent_usermessage(user)
            self.assertFalse(um.flags.mentioned)

    def test_user_group_edit_policy_for_creating_and_deleting_user_group(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        def check_create_user_group(acting_user: str, error_msg: Optional[str] = None) -> None:
            self.login(acting_user)
            params = {
                "name": "support",
                "members": orjson.dumps([hamlet.id]).decode(),
                "description": "Support Team",
            }
            result = self.client_post("/json/user_groups/create", info=params)
            if error_msg is None:
                self.assert_json_success(result)
                # One group already exists in the test database.
                self.assert_length(UserGroup.objects.filter(realm=realm), 2)
            else:
                self.assert_json_error(result, error_msg)

        def check_delete_user_group(acting_user: str, error_msg: Optional[str] = None) -> None:
            self.login(acting_user)
            user_group = UserGroup.objects.get(name="support")
            result = self.client_delete(f"/json/user_groups/{user_group.id}")
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_length(UserGroup.objects.filter(realm=realm), 1)
            else:
                self.assert_json_error(result, error_msg)

        realm = hamlet.realm

        # Check only admins are allowed to create/delete user group. Admins are allowed even if
        # they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_ADMINS_ONLY,
            acting_user=None,
        )
        check_create_user_group("shiva", "Insufficient permission")
        check_create_user_group("iago")

        check_delete_user_group("shiva", "Insufficient permission")
        check_delete_user_group("iago")

        # Check moderators are allowed to create/delete user group but not members. Moderators are
        # allowed even if they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_MODERATORS_ONLY,
            acting_user=None,
        )
        check_create_user_group("cordelia", "Insufficient permission")
        check_create_user_group("shiva")

        check_delete_user_group("hamlet", "Insufficient permission")
        check_delete_user_group("shiva")

        # Check only members are allowed to create the user group and they are allowed to delete
        # a user group only if they are a member of that group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )
        check_create_user_group("polonius", "Not allowed for guest users")
        check_create_user_group("cordelia")

        check_delete_user_group("polonius", "Not allowed for guest users")
        check_delete_user_group("cordelia", "Insufficient permission")
        check_delete_user_group("hamlet")

        # Check only full members are allowed to create the user group and they are allowed to delete
        # a user group only if they are a member of that group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_FULL_MEMBERS_ONLY,
            acting_user=None,
        )
        cordelia = self.example_user("cordelia")
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)

        cordelia.date_joined = timezone_now() - timedelta(days=9)
        cordelia.save()
        check_create_user_group("cordelia", "Insufficient permission")

        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        check_create_user_group("cordelia")

        hamlet.date_joined = timezone_now() - timedelta(days=9)
        hamlet.save()

        check_delete_user_group("cordelia", "Insufficient permission")
        check_delete_user_group("hamlet", "Insufficient permission")

        hamlet.date_joined = timezone_now() - timedelta(days=11)
        hamlet.save()
        check_delete_user_group("hamlet")

    def test_user_group_edit_policy_for_updating_user_groups(self) -> None:
        othello = self.example_user("othello")
        self.login("othello")
        params = {
            "name": "support",
            "members": orjson.dumps([othello.id]).decode(),
            "description": "Support team",
        }
        self.client_post("/json/user_groups/create", info=params)
        user_group = UserGroup.objects.get(name="support")

        def check_update_user_group(
            new_name: str,
            new_description: str,
            acting_user: str,
            error_msg: Optional[str] = None,
        ) -> None:
            self.login(acting_user)
            params = {
                "name": new_name,
                "description": new_description,
            }
            result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        realm = othello.realm

        # Check only admins are allowed to update user group. Admins are allowed even if
        # they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_ADMINS_ONLY,
            acting_user=None,
        )
        check_update_user_group("help", "Troubleshooting team", "shiva", "Insufficient permission")
        check_update_user_group("help", "Troubleshooting team", "iago")

        # Check moderators are allowed to update user group but not members. Moderators are
        # allowed even if they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_MODERATORS_ONLY,
            acting_user=None,
        )
        check_update_user_group("support", "Support team", "othello", "Insufficient permission")
        check_update_user_group("support", "Support team", "iago")

        # Check only members are allowed to update the user group and only if belong to the
        # user group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )
        check_update_user_group(
            "help", "Troubleshooting team", "polonius", "Not allowed for guest users"
        )
        check_update_user_group(
            "help",
            "Troubleshooting team",
            "cordelia",
            "Insufficient permission",
        )
        check_update_user_group("help", "Troubleshooting team", "othello")

        # Check only full members are allowed to update the user group and only if belong to the
        # user group.
        do_set_realm_property(
            realm, "user_group_edit_policy", Realm.POLICY_FULL_MEMBERS_ONLY, acting_user=None
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        othello = self.example_user("othello")
        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()

        cordelia = self.example_user("cordelia")
        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        check_update_user_group(
            "support",
            "Support team",
            "cordelia",
            "Insufficient permission",
        )
        check_update_user_group("support", "Support team", "othello", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        check_update_user_group("support", "Support team", "othello")

    def test_user_group_edit_policy_for_updating_members(self) -> None:
        user_group = self.create_user_group_for_test("support")
        aaron = self.example_user("aaron")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        def check_adding_members_to_group(
            acting_user: str, error_msg: Optional[str] = None
        ) -> None:
            self.login(acting_user)
            params = {"add": orjson.dumps([aaron.id]).decode()}
            result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
            if error_msg is None:
                self.assert_json_success(result)
                self.assertEqual(
                    UserGroupMembership.objects.filter(user_group=user_group).count(), 2
                )
                members = get_direct_memberships_of_users(user_group, [aaron, othello])
                self.assert_length(members, 2)
            else:
                self.assert_json_error(result, error_msg)

        def check_removing_members_from_group(
            acting_user: str, error_msg: Optional[str] = None
        ) -> None:
            self.login(acting_user)
            params = {"delete": orjson.dumps([aaron.id]).decode()}
            result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
            if error_msg is None:
                self.assert_json_success(result)
                self.assertEqual(
                    UserGroupMembership.objects.filter(user_group=user_group).count(), 1
                )
                members = get_direct_memberships_of_users(user_group, [aaron, othello])
                self.assert_length(members, 1)
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")
        # Check only admins are allowed to add/remove users from the group. Admins are allowed even if
        # they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_ADMINS_ONLY,
            acting_user=None,
        )
        check_adding_members_to_group("shiva", "Insufficient permission")
        check_adding_members_to_group("iago")

        check_removing_members_from_group("shiva", "Insufficient permission")
        check_removing_members_from_group("iago")

        # Check moderators are allowed to add/remove users from the group but not members. Moderators are
        # allowed even if they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_MODERATORS_ONLY,
            acting_user=None,
        )
        check_adding_members_to_group("cordelia", "Insufficient permission")
        check_adding_members_to_group("shiva")

        check_removing_members_from_group("hamlet", "Insufficient permission")
        check_removing_members_from_group("shiva")

        # Check only members are allowed to add/remove users in the group and only if belong to the
        # user group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_MEMBERS_ONLY,
            acting_user=None,
        )
        check_adding_members_to_group("polonius", "Not allowed for guest users")
        check_adding_members_to_group("cordelia", "Insufficient permission")
        check_adding_members_to_group("othello")

        check_removing_members_from_group("polonius", "Not allowed for guest users")
        check_removing_members_from_group("cordelia", "Insufficient permission")
        check_removing_members_from_group("othello")

        # Check only full members are allowed to add/remove users in the group and only if belong to the
        # user group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_FULL_MEMBERS_ONLY,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)

        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()
        check_adding_members_to_group("cordelia", "Insufficient permission")

        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        check_adding_members_to_group("cordelia", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        check_adding_members_to_group("othello")

        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()

        check_removing_members_from_group("cordelia", "Insufficient permission")
        check_removing_members_from_group("othello", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        check_removing_members_from_group("othello")

    def test_editing_system_user_groups(self) -> None:
        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        aaron = self.example_user("aaron")
        members = [iago, othello]

        user_group = create_user_group(
            "Full members",
            members,
            iago.realm,
            description="Full members user group",
            is_system_group=True,
        )

        def check_support_group_permission(acting_user: UserProfile) -> None:
            self.login_user(acting_user)
            params = {
                "name": "Full members user group",
                "description": "Full members system user group.",
            }
            result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
            self.assert_json_error(result, "Insufficient permission")

            params = {"add": orjson.dumps([aaron.id]).decode()}
            result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
            self.assert_json_error(result, "Insufficient permission")

            params = {"delete": orjson.dumps([othello.id]).decode()}
            result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
            self.assert_json_error(result, "Insufficient permission")

        check_support_group_permission(desdemona)
        check_support_group_permission(iago)
        check_support_group_permission(othello)
