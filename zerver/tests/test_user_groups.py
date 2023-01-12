from datetime import timedelta
from typing import Optional
from unittest import mock

import orjson
from django.utils.timezone import now as timezone_now

from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.user_groups import promote_new_full_members
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_usermessage
from zerver.lib.user_groups import (
    create_user_group,
    get_direct_memberships_of_users,
    get_direct_user_groups,
    get_recursive_group_members,
    get_recursive_membership_groups,
    get_recursive_subgroups,
    is_user_in_group,
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
        return create_user_group(group_name, members, realm, acting_user=None)

    def test_user_groups_in_realm_serialized(self) -> None:
        realm = get_realm("zulip")
        user_group = UserGroup.objects.filter(realm=realm).first()
        assert user_group is not None
        membership = UserGroupMembership.objects.filter(user_group=user_group).values_list(
            "user_profile_id", flat=True
        )
        empty_user_group = create_user_group("newgroup", [], realm, acting_user=None)

        user_groups = user_groups_in_realm_serialized(realm)
        self.assert_length(user_groups, 9)
        self.assertEqual(user_groups[0]["id"], user_group.id)
        self.assertEqual(user_groups[0]["name"], UserGroup.OWNERS_GROUP_NAME)
        self.assertEqual(user_groups[0]["description"], "Owners of this organization")
        self.assertEqual(set(user_groups[0]["members"]), set(membership))
        self.assertEqual(user_groups[0]["direct_subgroup_ids"], [])

        admins_system_group = UserGroup.objects.get(
            name=UserGroup.ADMINISTRATORS_GROUP_NAME, realm=realm
        )
        self.assertEqual(user_groups[1]["id"], admins_system_group.id)
        # Check that owners system group is present in "direct_subgroup_ids"
        self.assertEqual(user_groups[1]["direct_subgroup_ids"], [user_group.id])

        self.assertEqual(user_groups[8]["id"], empty_user_group.id)
        self.assertEqual(user_groups[8]["name"], "newgroup")
        self.assertEqual(user_groups[8]["description"], "")
        self.assertEqual(user_groups[8]["members"], [])

    def test_get_direct_user_groups(self) -> None:
        othello = self.example_user("othello")
        self.create_user_group_for_test("support")
        user_groups = get_direct_user_groups(othello)
        self.assert_length(user_groups, 3)
        # othello is a direct member of two role-based system groups also.
        user_group_names = [group.name for group in user_groups]
        self.assertEqual(
            set(user_group_names),
            {"support", UserGroup.MEMBERS_GROUP_NAME, UserGroup.FULL_MEMBERS_GROUP_NAME},
        )

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

        self.assertIn(leadership_group, list(get_recursive_membership_groups(desdemona)))
        self.assertIn(staff_group, list(get_recursive_membership_groups(desdemona)))
        self.assertIn(everyone_group, list(get_recursive_membership_groups(desdemona)))

        self.assertIn(staff_group, list(get_recursive_membership_groups(iago)))
        self.assertIn(everyone_group, list(get_recursive_membership_groups(iago)))

        self.assertIn(everyone_group, list(get_recursive_membership_groups(shiva)))

    def test_subgroups_of_role_based_system_groups(self) -> None:
        realm = get_realm("zulip")
        owners_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.OWNERS_GROUP_NAME, is_system_group=True
        )
        admins_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.ADMINISTRATORS_GROUP_NAME, is_system_group=True
        )
        moderators_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.MODERATORS_GROUP_NAME, is_system_group=True
        )
        full_members_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.FULL_MEMBERS_GROUP_NAME, is_system_group=True
        )
        members_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.MEMBERS_GROUP_NAME, is_system_group=True
        )
        everyone_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.EVERYONE_GROUP_NAME, is_system_group=True
        )
        everyone_on_internet_group = UserGroup.objects.get(
            realm=realm,
            name=UserGroup.EVERYONE_ON_INTERNET_GROUP_NAME,
            is_system_group=True,
        )

        self.assertCountEqual(list(get_recursive_subgroups(owners_group)), [owners_group])
        self.assertCountEqual(
            list(get_recursive_subgroups(admins_group)), [owners_group, admins_group]
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(moderators_group)),
            [owners_group, admins_group, moderators_group],
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(full_members_group)),
            [owners_group, admins_group, moderators_group, full_members_group],
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(members_group)),
            [owners_group, admins_group, moderators_group, full_members_group, members_group],
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(everyone_group)),
            [
                owners_group,
                admins_group,
                moderators_group,
                full_members_group,
                members_group,
                everyone_group,
            ],
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(everyone_on_internet_group)),
            [
                owners_group,
                admins_group,
                moderators_group,
                full_members_group,
                members_group,
                everyone_group,
                everyone_on_internet_group,
            ],
        )

    def test_is_user_in_group(self) -> None:
        realm = get_realm("zulip")
        shiva = self.example_user("shiva")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        moderators_group = UserGroup.objects.get(
            name=UserGroup.MODERATORS_GROUP_NAME, realm=realm, is_system_group=True
        )
        administrators_group = UserGroup.objects.get(
            name=UserGroup.ADMINISTRATORS_GROUP_NAME, realm=realm, is_system_group=True
        )

        self.assertTrue(is_user_in_group(moderators_group, shiva))

        # Iago is member of a subgroup of moderators group.
        self.assertTrue(is_user_in_group(moderators_group, iago))
        self.assertFalse(is_user_in_group(moderators_group, iago, direct_member_only=True))
        self.assertTrue(is_user_in_group(administrators_group, iago, direct_member_only=True))

        self.assertFalse(is_user_in_group(moderators_group, hamlet))
        self.assertFalse(is_user_in_group(moderators_group, hamlet, direct_member_only=True))


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
        self.assert_length(UserGroup.objects.filter(realm=hamlet.realm), 9)

        # Test invalid member error
        params = {
            "name": "backend",
            "members": orjson.dumps([1111]).decode(),
            "description": "Backend team",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Invalid user ID: 1111")
        self.assert_length(UserGroup.objects.filter(realm=hamlet.realm), 9)

        # Test we cannot create group with same name again
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group 'support' already exists.")
        self.assert_length(UserGroup.objects.filter(realm=hamlet.realm), 9)

    def test_user_group_get(self) -> None:
        # Test success
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        result = self.client_get("/json/user_groups")
        response_dict = self.assert_json_success(result)
        self.assert_length(
            response_dict["user_groups"], UserGroup.objects.filter(realm=user_profile.realm).count()
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

        lear_realm = get_realm("lear")
        lear_test_group = create_user_group(
            "test", [self.lear_user("cordelia")], lear_realm, acting_user=None
        )
        result = self.client_patch(f"/json/user_groups/{lear_test_group.id}", info=params)
        self.assert_json_error(result, "Invalid user group")

    def test_user_group_update_to_already_existing_name(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        realm = get_realm("zulip")
        support_user_group = create_user_group("support", [hamlet], realm, acting_user=None)
        marketing_user_group = create_user_group("marketing", [hamlet], realm, acting_user=None)

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
        self.assertEqual(UserGroup.objects.filter(realm=hamlet.realm).count(), 9)
        self.assertEqual(UserGroupMembership.objects.count(), 47)
        result = self.client_delete(f"/json/user_groups/{user_group.id}")
        self.assert_json_success(result)
        self.assertEqual(UserGroup.objects.filter(realm=hamlet.realm).count(), 8)
        self.assertEqual(UserGroupMembership.objects.count(), 46)
        # Test when invalid user group is supplied
        result = self.client_delete("/json/user_groups/1111")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_test_group = create_user_group(
            "test", [self.lear_user("cordelia")], lear_realm, acting_user=None
        )
        result = self.client_delete(f"/json/user_groups/{lear_test_group.id}")
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
            name=group_name, members=list(support_team), realm=realm, acting_user=None
        )

        payload = dict(
            type="stream",
            to=orjson.dumps(stream_name).decode(),
            topic="whatever",
            content=content_with_group_mention,
        )

        result = self.api_post(sender, "/api/v1/messages", payload)

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
                self.assert_length(UserGroup.objects.filter(realm=realm), 9)
            else:
                self.assert_json_error(result, error_msg)

        def check_delete_user_group(acting_user: str, error_msg: Optional[str] = None) -> None:
            self.login(acting_user)
            user_group = UserGroup.objects.get(name="support")
            result = self.client_delete(f"/json/user_groups/{user_group.id}")
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_length(UserGroup.objects.filter(realm=realm), 8)
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

        user_group = UserGroup.objects.get(
            realm=iago.realm, name=UserGroup.FULL_MEMBERS_GROUP_NAME, is_system_group=True
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

    def test_promote_new_full_members(self) -> None:
        realm = get_realm("zulip")

        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()

        hamlet.date_joined = timezone_now() - timedelta(days=8)
        hamlet.save()

        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        full_members_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.FULL_MEMBERS_GROUP_NAME, is_system_group=True
        )

        self.assertTrue(
            UserGroupMembership.objects.filter(
                user_profile=cordelia, user_group=full_members_group
            ).exists()
        )
        self.assertFalse(
            UserGroupMembership.objects.filter(
                user_profile=hamlet, user_group=full_members_group
            ).exists()
        )

        current_time = timezone_now()
        with mock.patch(
            "zerver.actions.user_groups.timezone_now", return_value=current_time + timedelta(days=3)
        ):
            promote_new_full_members()

        self.assertTrue(
            UserGroupMembership.objects.filter(
                user_profile=cordelia, user_group=full_members_group
            ).exists()
        )
        self.assertTrue(
            UserGroupMembership.objects.filter(
                user_profile=hamlet, user_group=full_members_group
            ).exists()
        )

    def test_updating_subgroups_of_user_group(self) -> None:
        realm = get_realm("zulip")
        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        leadership_group = create_user_group(
            "leadership", [desdemona, iago, hamlet], realm, acting_user=None
        )
        support_group = create_user_group("support", [hamlet, othello], realm, acting_user=None)

        self.login("cordelia")
        # Non-admin and non-moderators who are not a member of group cannot add or remove subgroups.
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Insufficient permission")

        self.login("iago")
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        self.login("shiva")
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        self.login("hamlet")
        # Non-admin and non-moderators who are a member of the user group can add or remove subgroups.
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        # Users need not be part of the subgroup to add or remove it from a user group.
        self.login("othello")
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)

        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(
            result,
            ("User group {group_id} is not a subgroup of this group.").format(
                group_id=leadership_group.id
            ),
        )

        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)

        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(
            result,
            ("User group {group_id} is already a subgroup of this group.").format(
                group_id=leadership_group.id
            ),
        )

        lear_realm = get_realm("lear")
        lear_test_group = create_user_group(
            "test", [self.lear_user("cordelia")], lear_realm, acting_user=None
        )
        result = self.client_post(f"/json/user_groups/{lear_test_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Invalid user group")

        # Invalid subgroup id will raise an error.
        params = {"add": orjson.dumps([leadership_group.id, 1111]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Invalid user group ID: 1111")

        # Test when nothing is provided
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info={})
        self.assert_json_error(result, 'Nothing to do. Specify at least one of "add" or "delete".')

    def test_get_is_user_group_member_status(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        admins_group = UserGroup.objects.get(
            realm=realm, name=UserGroup.ADMINISTRATORS_GROUP_NAME, is_system_group=True
        )

        # Invalid user ID.
        result = self.client_get(f"/json/user_groups/{admins_group.id}/members/1111")
        self.assert_json_error(result, "No such user")

        # Invalid user group ID.
        result = self.client_get(f"/json/user_groups/1111/members/{iago.id}")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_cordelia = self.lear_user("cordelia")
        lear_test_group = create_user_group("test", [lear_cordelia], lear_realm, acting_user=None)
        result = self.client_get(
            f"/json/user_groups/{lear_test_group.id}/members/{lear_cordelia.id}"
        )
        self.assert_json_error(result, "Invalid user group")

        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{admins_group.id}/members/{othello.id}").content
        )
        self.assertFalse(result_dict["is_user_group_member"])

        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{admins_group.id}/members/{iago.id}").content
        )
        self.assertTrue(result_dict["is_user_group_member"])

        # Checking membership of not a direct member but member of a subgroup.
        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{admins_group.id}/members/{desdemona.id}").content
        )
        self.assertTrue(result_dict["is_user_group_member"])

        # Checking membership of not a direct member but member of a subgroup when passing
        # recursive parameter as False.
        params = {"direct_member_only": orjson.dumps(True).decode()}
        result_dict = orjson.loads(
            self.client_get(
                f"/json/user_groups/{admins_group.id}/members/{desdemona.id}", info=params
            ).content
        )
        self.assertFalse(result_dict["is_user_group_member"])

        # Logging in with a user not part of the group.
        self.login("hamlet")

        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{admins_group.id}/members/{iago.id}").content
        )
        self.assertTrue(result_dict["is_user_group_member"])

        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{admins_group.id}/members/{othello.id}").content
        )
        self.assertFalse(result_dict["is_user_group_member"])

    def test_get_user_group_members(self) -> None:
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        shiva = self.example_user("shiva")
        moderators_group = UserGroup.objects.get(
            name=UserGroup.MODERATORS_GROUP_NAME, realm=realm, is_system_group=True
        )
        self.login("iago")

        # Test invalid user group id
        result = self.client_get("/json/user_groups/1111/members")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_test_group = create_user_group(
            "test", [self.lear_user("cordelia")], lear_realm, acting_user=None
        )
        result = self.client_get(f"/json/user_groups/{lear_test_group.id}/members")
        self.assert_json_error(result, "Invalid user group")

        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/members").content
        )
        self.assertCountEqual(result_dict["members"], [desdemona.id, iago.id, shiva.id])

        params = {"direct_member_only": orjson.dumps(True).decode()}
        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/members", info=params).content
        )
        self.assertCountEqual(result_dict["members"], [shiva.id])

        # User not part of a group can also get its members.
        self.login("hamlet")
        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/members").content
        )
        self.assertCountEqual(result_dict["members"], [desdemona.id, iago.id, shiva.id])

        params = {"direct_member_only": orjson.dumps(True).decode()}
        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/members", info=params).content
        )
        self.assertCountEqual(result_dict["members"], [shiva.id])

    def test_get_subgroups_of_user_group(self) -> None:
        realm = get_realm("zulip")
        owners_group = UserGroup.objects.get(
            name=UserGroup.OWNERS_GROUP_NAME, realm=realm, is_system_group=True
        )
        admins_group = UserGroup.objects.get(
            name=UserGroup.ADMINISTRATORS_GROUP_NAME, realm=realm, is_system_group=True
        )
        moderators_group = UserGroup.objects.get(
            name=UserGroup.MODERATORS_GROUP_NAME, realm=realm, is_system_group=True
        )
        self.login("iago")

        # Test invalid user group id
        result = self.client_get("/json/user_groups/1111/subgroups")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_test_group = create_user_group(
            "test", [self.lear_user("cordelia")], lear_realm, acting_user=None
        )
        result = self.client_get(f"/json/user_groups/{lear_test_group.id}/subgroups")
        self.assert_json_error(result, "Invalid user group")

        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/subgroups").content
        )
        self.assertEqual(result_dict["subgroups"], [admins_group.id, owners_group.id])

        params = {"direct_subgroup_only": orjson.dumps(True).decode()}
        result_dict = orjson.loads(
            self.client_get(
                f"/json/user_groups/{moderators_group.id}/subgroups", info=params
            ).content
        )
        self.assertCountEqual(result_dict["subgroups"], [admins_group.id])

        # User not part of a group can also get its subgroups.
        self.login("hamlet")
        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/subgroups").content
        )
        self.assertEqual(result_dict["subgroups"], [admins_group.id, owners_group.id])

        params = {"direct_subgroup_only": orjson.dumps(True).decode()}
        result_dict = orjson.loads(
            self.client_get(
                f"/json/user_groups/{moderators_group.id}/subgroups", info=params
            ).content
        )
        self.assertCountEqual(result_dict["subgroups"], [admins_group.id])
