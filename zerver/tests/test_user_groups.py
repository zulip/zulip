from collections.abc import Iterable
from datetime import timedelta
from unittest import mock

import orjson
import time_machine
from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.actions.create_realm import do_create_realm
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.user_groups import (
    add_subgroups_to_user_group,
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    check_add_user_group,
    create_user_group_in_database,
    do_change_user_group_permission_setting,
    promote_new_full_members,
)
from zerver.actions.users import do_deactivate_user
from zerver.lib.create_user import create_user
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_usermessage
from zerver.lib.user_groups import (
    AnonymousSettingGroupDict,
    get_direct_user_groups,
    get_recursive_group_members,
    get_recursive_membership_groups,
    get_recursive_strict_subgroups,
    get_recursive_subgroups,
    get_role_based_system_groups_dict,
    get_subgroup_ids,
    get_user_group_member_ids,
    has_user_group_access,
    is_any_user_in_group,
    is_user_in_group,
    user_groups_in_realm_serialized,
)
from zerver.models import (
    GroupGroupMembership,
    NamedUserGroup,
    Realm,
    UserGroup,
    UserGroupMembership,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realms import CommonPolicyEnum, get_realm


class UserGroupTestCase(ZulipTestCase):
    def assert_user_membership(
        self, user_group: NamedUserGroup, members: Iterable[UserProfile]
    ) -> None:
        user_ids = get_user_group_member_ids(user_group, direct_member_only=True)
        self.assertSetEqual(set(user_ids), {member.id for member in members})

    def assert_subgroup_membership(
        self, user_group: NamedUserGroup, members: Iterable[UserGroup]
    ) -> None:
        subgroup_ids = get_subgroup_ids(user_group, direct_subgroup_only=True)
        self.assertSetEqual(set(subgroup_ids), {member.id for member in members})

    def create_user_group_for_test(self, group_name: str) -> NamedUserGroup:
        members = [self.example_user("othello")]
        return check_add_user_group(get_realm("zulip"), group_name, members, acting_user=None)

    def test_user_groups_in_realm_serialized(self) -> None:
        realm = get_realm("zulip")
        user_group = NamedUserGroup.objects.filter(realm=realm).first()
        assert user_group is not None
        empty_user_group = check_add_user_group(realm, "newgroup", [], acting_user=None)

        user_groups = user_groups_in_realm_serialized(realm)
        self.assert_length(user_groups, 10)
        self.assertEqual(user_groups[0]["id"], user_group.id)
        self.assertEqual(user_groups[0]["name"], SystemGroups.NOBODY)
        self.assertEqual(user_groups[0]["description"], "Nobody")
        self.assertEqual(user_groups[0]["members"], [])
        self.assertEqual(user_groups[0]["direct_subgroup_ids"], [])
        self.assertEqual(user_groups[0]["can_manage_group"], user_group.id)
        self.assertEqual(user_groups[0]["can_mention_group"], user_group.id)

        owners_system_group = NamedUserGroup.objects.get(name=SystemGroups.OWNERS, realm=realm)
        membership = UserGroupMembership.objects.filter(user_group=owners_system_group).values_list(
            "user_profile_id", flat=True
        )
        self.assertEqual(user_groups[1]["id"], owners_system_group.id)
        self.assertEqual(user_groups[1]["name"], SystemGroups.OWNERS)
        self.assertEqual(user_groups[1]["description"], "Owners of this organization")
        self.assertEqual(set(user_groups[1]["members"]), set(membership))
        self.assertEqual(user_groups[1]["direct_subgroup_ids"], [])
        self.assertEqual(user_groups[1]["can_manage_group"], user_group.id)
        self.assertEqual(user_groups[1]["can_mention_group"], user_group.id)

        admins_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm
        )
        self.assertEqual(user_groups[2]["id"], admins_system_group.id)
        # Check that owners system group is present in "direct_subgroup_ids"
        self.assertEqual(user_groups[2]["direct_subgroup_ids"], [owners_system_group.id])

        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        self.assertEqual(user_groups[9]["id"], empty_user_group.id)
        self.assertEqual(user_groups[9]["name"], "newgroup")
        self.assertEqual(user_groups[9]["description"], "")
        self.assertEqual(user_groups[9]["members"], [])
        self.assertEqual(user_groups[9]["can_manage_group"], user_group.id)
        self.assertEqual(user_groups[9]["can_mention_group"], everyone_group.id)

        othello = self.example_user("othello")
        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [othello], [admins_system_group, hamletcharacters_group]
        )
        new_user_group = check_add_user_group(
            realm,
            "newgroup2",
            [othello],
            group_settings_map={
                "can_manage_group": setting_group,
                "can_mention_group": setting_group,
            },
            acting_user=None,
        )
        user_groups = user_groups_in_realm_serialized(realm)
        self.assertEqual(user_groups[10]["id"], new_user_group.id)
        self.assertEqual(user_groups[10]["name"], "newgroup2")
        self.assertEqual(user_groups[10]["description"], "")
        self.assertEqual(user_groups[10]["members"], [othello.id])

        assert isinstance(user_groups[10]["can_manage_group"], AnonymousSettingGroupDict)
        self.assertEqual(user_groups[10]["can_manage_group"].direct_members, [othello.id])
        self.assertCountEqual(
            user_groups[10]["can_manage_group"].direct_subgroups,
            [admins_system_group.id, hamletcharacters_group.id],
        )

        assert isinstance(user_groups[10]["can_mention_group"], AnonymousSettingGroupDict)
        self.assertEqual(user_groups[10]["can_mention_group"].direct_members, [othello.id])
        self.assertCountEqual(
            user_groups[10]["can_mention_group"].direct_subgroups,
            [admins_system_group.id, hamletcharacters_group.id],
        )

    def test_get_direct_user_groups(self) -> None:
        othello = self.example_user("othello")
        self.create_user_group_for_test("support")
        user_groups = get_direct_user_groups(othello)
        self.assert_length(user_groups, 3)
        # othello is a direct member of two role-based system groups also.
        user_group_names = [group.named_user_group.name for group in user_groups]
        self.assertEqual(
            set(user_group_names),
            {"support", SystemGroups.MEMBERS, SystemGroups.FULL_MEMBERS},
        )

    def test_recursive_queries_for_user_groups(self) -> None:
        realm = get_realm("zulip")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        shiva = self.example_user("shiva")

        leadership_group = check_add_user_group(realm, "Leadership", [desdemona], acting_user=None)

        staff_group = check_add_user_group(realm, "Staff", [iago], acting_user=None)
        GroupGroupMembership.objects.create(supergroup=staff_group, subgroup=leadership_group)

        everyone_group = check_add_user_group(realm, "Everyone", [shiva], acting_user=None)
        GroupGroupMembership.objects.create(supergroup=everyone_group, subgroup=staff_group)

        self.assertCountEqual(
            list(get_recursive_subgroups(leadership_group)), [leadership_group.usergroup_ptr]
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(staff_group)),
            [leadership_group.usergroup_ptr, staff_group.usergroup_ptr],
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(everyone_group)),
            [
                leadership_group.usergroup_ptr,
                staff_group.usergroup_ptr,
                everyone_group.usergroup_ptr,
            ],
        )

        self.assertCountEqual(list(get_recursive_strict_subgroups(leadership_group)), [])
        self.assertCountEqual(list(get_recursive_strict_subgroups(staff_group)), [leadership_group])
        self.assertCountEqual(
            list(get_recursive_strict_subgroups(everyone_group)),
            [leadership_group, staff_group],
        )

        self.assertCountEqual(list(get_recursive_group_members(leadership_group)), [desdemona])
        self.assertCountEqual(list(get_recursive_group_members(staff_group)), [desdemona, iago])
        self.assertCountEqual(
            list(get_recursive_group_members(everyone_group)), [desdemona, iago, shiva]
        )

        self.assertIn(leadership_group.usergroup_ptr, get_recursive_membership_groups(desdemona))
        self.assertIn(staff_group.usergroup_ptr, get_recursive_membership_groups(desdemona))
        self.assertIn(everyone_group.usergroup_ptr, get_recursive_membership_groups(desdemona))

        self.assertIn(staff_group.usergroup_ptr, get_recursive_membership_groups(iago))
        self.assertIn(everyone_group.usergroup_ptr, get_recursive_membership_groups(iago))

        self.assertIn(everyone_group.usergroup_ptr, get_recursive_membership_groups(shiva))

    def test_subgroups_of_role_based_system_groups(self) -> None:
        realm = get_realm("zulip")
        owners_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.OWNERS, is_system_group=True
        )
        admins_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.ADMINISTRATORS, is_system_group=True
        )
        moderators_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.MODERATORS, is_system_group=True
        )
        full_members_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.FULL_MEMBERS, is_system_group=True
        )
        members_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.MEMBERS, is_system_group=True
        )
        everyone_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.EVERYONE, is_system_group=True
        )
        everyone_on_internet_group = NamedUserGroup.objects.get(
            realm=realm,
            name=SystemGroups.EVERYONE_ON_INTERNET,
            is_system_group=True,
        )

        self.assertCountEqual(list(get_recursive_strict_subgroups(owners_group)), [])
        self.assertCountEqual(list(get_recursive_strict_subgroups(admins_group)), [owners_group])
        self.assertCountEqual(
            list(get_recursive_strict_subgroups(moderators_group)),
            [owners_group, admins_group],
        )
        self.assertCountEqual(
            list(get_recursive_strict_subgroups(full_members_group)),
            [owners_group, admins_group, moderators_group],
        )
        self.assertCountEqual(
            list(get_recursive_strict_subgroups(members_group)),
            [owners_group, admins_group, moderators_group, full_members_group],
        )
        self.assertCountEqual(
            list(get_recursive_strict_subgroups(everyone_group)),
            [
                owners_group,
                admins_group,
                moderators_group,
                full_members_group,
                members_group,
            ],
        )
        self.assertCountEqual(
            list(get_recursive_strict_subgroups(everyone_on_internet_group)),
            [
                owners_group,
                admins_group,
                moderators_group,
                full_members_group,
                members_group,
                everyone_group,
            ],
        )

    def test_is_user_in_group(self) -> None:
        realm = get_realm("zulip")
        shiva = self.example_user("shiva")
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        administrators_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )

        self.assertTrue(is_user_in_group(moderators_group, shiva))

        # Iago is member of a subgroup of moderators group.
        self.assertTrue(is_user_in_group(moderators_group, iago))
        self.assertFalse(is_user_in_group(moderators_group, iago, direct_member_only=True))
        self.assertTrue(is_user_in_group(administrators_group, iago, direct_member_only=True))

        self.assertFalse(is_user_in_group(moderators_group, hamlet))
        self.assertFalse(is_user_in_group(moderators_group, hamlet, direct_member_only=True))

    def test_is_any_user_in_group(self) -> None:
        realm = get_realm("zulip")
        shiva = self.example_user("shiva").id
        iago = self.example_user("iago").id
        hamlet = self.example_user("hamlet").id
        polonius = self.example_user("polonius").id

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        administrators_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )

        self.assertTrue(is_any_user_in_group(moderators_group, [shiva, hamlet, polonius]))

        # Iago is member of a subgroup of moderators group.
        self.assertTrue(is_any_user_in_group(moderators_group, [iago, hamlet, polonius]))
        self.assertFalse(
            is_any_user_in_group(
                moderators_group, [iago, hamlet, polonius], direct_member_only=True
            )
        )
        self.assertTrue(
            is_any_user_in_group(
                administrators_group, [iago, shiva, hamlet], direct_member_only=True
            )
        )

        self.assertFalse(is_any_user_in_group(moderators_group, [hamlet, polonius]))
        self.assertFalse(is_any_user_in_group(moderators_group, [hamlet], direct_member_only=True))

    def test_has_user_group_access_to_subgroup(self) -> None:
        iago = self.example_user("iago")
        zulip_realm = get_realm("zulip")
        zulip_group = check_add_user_group(zulip_realm, "zulip", [], acting_user=None)
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=zulip_realm, is_system_group=True
        )

        lear_realm = get_realm("lear")
        lear_group = check_add_user_group(lear_realm, "test", [], acting_user=None)

        self.assertFalse(has_user_group_access(lear_group, iago, for_read=False, as_subgroup=True))
        self.assertTrue(has_user_group_access(zulip_group, iago, for_read=False, as_subgroup=True))
        self.assertTrue(
            has_user_group_access(moderators_group, iago, for_read=False, as_subgroup=True)
        )


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
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        # Check default value of settings.
        everyone_system_group = NamedUserGroup.objects.get(
            name="role:everyone", realm=hamlet.realm, is_system_group=True
        )
        nobody_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=hamlet.realm, is_system_group=True
        )
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertEqual(support_group.can_manage_group, nobody_system_group.usergroup_ptr)
        self.assertEqual(support_group.can_mention_group, everyone_system_group.usergroup_ptr)

        # Test invalid member error
        params = {
            "name": "backend",
            "members": orjson.dumps([1111]).decode(),
            "description": "Backend team",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Invalid user ID: 1111")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        # Test we cannot create group with same name again
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group 'support' already exists.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        # Test we cannot create group with same name again
        params = {
            "name": "a" * (NamedUserGroup.MAX_NAME_LENGTH + 1),
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Test group",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name cannot exceed 100 characters.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        # Test emtpty group name.
        params = {
            "name": "",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Test empty group",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name can't be empty!")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        # Test invalid prefixes for user group name.
        params = {
            "name": "@test",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Test group",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name cannot start with '@'.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        params["name"] = "role:manager"
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name cannot start with 'role:'.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        params["name"] = "user:1"
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name cannot start with 'user:'.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        params["name"] = "stream:1"
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name cannot start with 'stream:'.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        params["name"] = "channel:1"
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name cannot start with 'channel:'.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

    def do_test_set_group_setting_during_user_group_creation(self, setting_name: str) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        # Delete all existing user groups except the hamletcharacters group
        NamedUserGroup.objects.exclude(name="hamletcharacters").filter(
            is_system_group=False
        ).delete()

        permission_configuration = NamedUserGroup.GROUP_PERMISSION_SETTINGS[setting_name]
        leadership_group = check_add_user_group(
            hamlet.realm, "leadership", [hamlet], acting_user=None
        )
        moderators_group = NamedUserGroup.objects.get(
            name="role:moderators", realm=hamlet.realm, is_system_group=True
        )
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        params[setting_name] = orjson.dumps(moderators_group.id).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertEqual(getattr(support_group, setting_name), moderators_group.usergroup_ptr)

        params = {
            "name": "test",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Test group",
        }
        params[setting_name] = orjson.dumps(leadership_group.id).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        test_group = NamedUserGroup.objects.get(name="test", realm=hamlet.realm)
        self.assertEqual(getattr(test_group, setting_name), leadership_group.usergroup_ptr)

        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", realm=hamlet.realm, is_system_group=True
        )
        params = {
            "name": "marketing",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Marketing team",
        }
        params[setting_name] = orjson.dumps(nobody_group.id).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        marketing_group = NamedUserGroup.objects.get(name="marketing", realm=hamlet.realm)
        self.assertEqual(getattr(marketing_group, setting_name), nobody_group.usergroup_ptr)

        othello = self.example_user("othello")
        params = {
            "name": "backend",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Backend team",
        }
        params[setting_name] = orjson.dumps(
            {
                "direct_members": [othello.id],
                "direct_subgroups": [leadership_group.id, moderators_group.id],
            }
        ).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        backend_group = NamedUserGroup.objects.get(name="backend", realm=hamlet.realm)
        self.assertCountEqual(
            list(getattr(backend_group, setting_name).direct_members.all()),
            [othello],
        )
        self.assertCountEqual(
            list(getattr(backend_group, setting_name).direct_subgroups.all()),
            [leadership_group, moderators_group],
        )

        params = {
            "name": "help",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Troubleshooting team",
        }
        params[setting_name] = orjson.dumps(
            {
                "direct_members": [],
                "direct_subgroups": [moderators_group.id],
            }
        ).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        help_group = NamedUserGroup.objects.get(name="help", realm=hamlet.realm)
        # We do not create a new UserGroup object in such case.
        self.assertEqual(getattr(help_group, setting_name).id, moderators_group.id)

        internet_group = NamedUserGroup.objects.get(
            name="role:internet", realm=hamlet.realm, is_system_group=True
        )
        params = {
            "name": "frontend",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Frontend team",
        }
        params[setting_name] = orjson.dumps(internet_group.id).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(
            result, f"'{setting_name}' setting cannot be set to 'role:internet' group."
        )

        owners_group = NamedUserGroup.objects.get(
            name="role:owners", realm=hamlet.realm, is_system_group=True
        )
        params = {
            "name": "frontend-team",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Frontend team",
        }
        params[setting_name] = orjson.dumps(owners_group.id).decode()
        result = self.client_post("/json/user_groups/create", info=params)

        if not permission_configuration.allow_owners_group:
            self.assert_json_error(
                result, f"'{setting_name}' setting cannot be set to 'role:owners' group."
            )
        else:
            self.assert_json_success(result)
            frontend_group = NamedUserGroup.objects.get(name="frontend-team", realm=hamlet.realm)
            self.assertEqual(getattr(frontend_group, setting_name), owners_group.usergroup_ptr)

        params = {
            "name": "frontend",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Frontend team",
        }
        params[setting_name] = orjson.dumps(1111).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Invalid user group")

        params = {
            "name": "frontend",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Frontend team",
        }
        params[setting_name] = orjson.dumps(
            {
                "direct_members": [1111],
                "direct_subgroups": [leadership_group.id, moderators_group.id],
            }
        ).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Invalid user ID: 1111")

        params = {
            "name": "frontend",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Frontend team",
        }
        params[setting_name] = orjson.dumps(
            {
                "direct_members": [othello.id],
                "direct_subgroups": [1111, moderators_group.id],
            }
        ).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Invalid user group ID: 1111")

        with self.settings(ALLOW_GROUP_VALUED_SETTINGS=False):
            params = {
                "name": "frontend",
                "members": orjson.dumps([hamlet.id]).decode(),
                "description": "Frontend team",
            }
            params[setting_name] = orjson.dumps(
                {
                    "direct_members": [othello.id],
                    "direct_subgroups": [moderators_group.id],
                }
            ).decode()
            result = self.client_post("/json/user_groups/create", info=params)
            self.assert_json_error(result, f"'{setting_name}' must be a system user group.")

            params = {
                "name": "frontend",
                "members": orjson.dumps([hamlet.id]).decode(),
                "description": "Frontend team",
            }
            params[setting_name] = orjson.dumps(
                {
                    "direct_members": [],
                    "direct_subgroups": [moderators_group.id],
                }
            ).decode()
            result = self.client_post("/json/user_groups/create", info=params)
            self.assert_json_success(result)
            frontend_group = NamedUserGroup.objects.get(name="frontend", realm=hamlet.realm)
            self.assertEqual(getattr(frontend_group, setting_name).id, moderators_group.id)

            params = {
                "name": "devops",
                "members": orjson.dumps([hamlet.id]).decode(),
                "description": "Devops team",
            }
            params[setting_name] = orjson.dumps(leadership_group.id).decode()
            result = self.client_post("/json/user_groups/create", info=params)
            if setting_name == "can_mention_group":
                self.assert_json_success(result)
                devops_group = NamedUserGroup.objects.get(name="devops", realm=hamlet.realm)
                self.assertEqual(getattr(devops_group, setting_name).id, leadership_group.id)
            else:
                self.assert_json_error(result, f"'{setting_name}' must be a system user group.")

    def test_set_group_settings_during_user_group_creation(self) -> None:
        for setting_name in NamedUserGroup.GROUP_PERMISSION_SETTINGS:
            self.do_test_set_group_setting_during_user_group_creation(setting_name)

    def test_user_group_get(self) -> None:
        # Test success
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        result = self.client_get("/json/user_groups")
        response_dict = self.assert_json_success(result)
        self.assert_length(
            response_dict["user_groups"],
            NamedUserGroup.objects.filter(realm=user_profile.realm).count(),
        )

    def test_can_edit_all_user_groups(self) -> None:
        def validation_func(user_profile: UserProfile) -> bool:
            return user_profile.can_edit_all_user_groups()

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
        user_group = NamedUserGroup.objects.get(name="support")
        # Test success
        params = {
            "name": "help",
            "description": "Troubleshooting team",
        }
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_success(result)
        user_group = NamedUserGroup.objects.get(id=user_group.id)
        self.assertEqual(user_group.name, "help")
        self.assertEqual(user_group.description, "Troubleshooting team")

        # Test when new data is not supplied.
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info={})
        self.assert_json_error(result, "No new data supplied")

        # Test when only one of name or description is supplied.
        params = {"name": "help team"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_success(result)
        user_group = NamedUserGroup.objects.get(id=user_group.id)
        self.assertEqual(user_group.name, "help team")
        self.assertEqual(user_group.description, "Troubleshooting team")

        # Test when invalid user group is supplied
        params = {"name": "help"}
        result = self.client_patch("/json/user_groups/1111", info=params)
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [self.lear_user("cordelia")], acting_user=None
        )
        result = self.client_patch(f"/json/user_groups/{lear_test_group.id}", info=params)
        self.assert_json_error(result, "Invalid user group")

        params = {"name": "a" * (NamedUserGroup.MAX_NAME_LENGTH + 1)}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_error(result, "User group name cannot exceed 100 characters.")

        # Test emtpty group name.
        params = {"name": ""}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_error(result, "User group name can't be empty!")

        # Test invalid prefixes for user group name.
        params = {"name": "@test"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_error(result, "User group name cannot start with '@'.")

        params = {"name": "role:manager"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_error(result, "User group name cannot start with 'role:'.")

        params = {"name": "user:1"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_error(result, "User group name cannot start with 'user:'.")

        params = {"name": "stream:1"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_error(result, "User group name cannot start with 'stream:'.")

        params = {"name": "channel:1"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_error(result, "User group name cannot start with 'channel:'.")

    def do_test_update_user_group_permission_settings(self, setting_name: str) -> None:
        hamlet = self.example_user("hamlet")
        permission_configuration = NamedUserGroup.GROUP_PERMISSION_SETTINGS[setting_name]

        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        marketing_group = NamedUserGroup.objects.get(name="marketing", realm=hamlet.realm)

        moderators_group = NamedUserGroup.objects.get(
            name="role:moderators", realm=hamlet.realm, is_system_group=True
        )

        self.login("hamlet")
        params = {}
        params[setting_name] = orjson.dumps(
            {
                "new": moderators_group.id,
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertEqual(getattr(support_group, setting_name), moderators_group.usergroup_ptr)

        params[setting_name] = orjson.dumps(
            {
                "new": marketing_group.id,
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertEqual(getattr(support_group, setting_name), marketing_group.usergroup_ptr)

        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", realm=hamlet.realm, is_system_group=True
        )
        params[setting_name] = orjson.dumps({"new": nobody_group.id}).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertEqual(getattr(support_group, setting_name), nobody_group.usergroup_ptr)

        othello = self.example_user("othello")
        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [othello.id],
                    "direct_subgroups": [moderators_group.id, marketing_group.id],
                }
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertCountEqual(
            list(getattr(support_group, setting_name).direct_members.all()),
            [othello],
        )
        self.assertCountEqual(
            list(getattr(support_group, setting_name).direct_subgroups.all()),
            [marketing_group, moderators_group],
        )

        prospero = self.example_user("prospero")
        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [othello.id, prospero.id],
                    "direct_subgroups": [moderators_group.id, marketing_group.id],
                }
            }
        ).decode()
        previous_setting_id = getattr(support_group, setting_name).id
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)

        # Test that the existing UserGroup object is updated.
        self.assertEqual(getattr(support_group, setting_name).id, previous_setting_id)
        self.assertCountEqual(
            list(getattr(support_group, setting_name).direct_members.all()),
            [othello, prospero],
        )
        self.assertCountEqual(
            list(getattr(support_group, setting_name).direct_subgroups.all()),
            [marketing_group, moderators_group],
        )

        params[setting_name] = orjson.dumps({"new": marketing_group.id}).decode()
        previous_setting_id = getattr(support_group, setting_name).id
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)

        # Test that the previous UserGroup object is deleted.
        self.assertFalse(UserGroup.objects.filter(id=previous_setting_id).exists())
        self.assertEqual(getattr(support_group, setting_name).id, marketing_group.id)

        owners_group = NamedUserGroup.objects.get(
            name="role:owners", realm=hamlet.realm, is_system_group=True
        )
        params[setting_name] = orjson.dumps({"new": owners_group.id}).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        if not permission_configuration.allow_owners_group:
            self.assert_json_error(
                result, f"'{setting_name}' setting cannot be set to 'role:owners' group."
            )
        else:
            self.assert_json_success(result)
            support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
            self.assertEqual(getattr(support_group, setting_name).id, owners_group.id)

        internet_group = NamedUserGroup.objects.get(
            name="role:internet", realm=hamlet.realm, is_system_group=True
        )
        params[setting_name] = orjson.dumps({"new": internet_group.id}).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(
            result, f"'{setting_name}' setting cannot be set to 'role:internet' group."
        )

        params[setting_name] = orjson.dumps({"new": 1111}).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Invalid user group")

        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [1111, othello.id],
                    "direct_subgroups": [moderators_group.id, marketing_group.id],
                }
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Invalid user ID: 1111")

        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [prospero.id, othello.id],
                    "direct_subgroups": [1111, marketing_group.id],
                }
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Invalid user group ID: 1111")

        # Test case when ALLOW_GROUP_VALUED_SETTINGS is False.
        with self.settings(ALLOW_GROUP_VALUED_SETTINGS=False):
            params[setting_name] = orjson.dumps(
                {
                    "new": {
                        "direct_members": [othello.id],
                        "direct_subgroups": [moderators_group.id, marketing_group.id],
                    }
                }
            ).decode()
            result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
            self.assert_json_error(result, f"'{setting_name}' must be a system user group.")

            params[setting_name] = orjson.dumps(
                {
                    "new": {
                        "direct_members": [],
                        "direct_subgroups": [moderators_group.id],
                    }
                }
            ).decode()
            result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
            self.assert_json_success(result)
            support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
            self.assertEqual(getattr(support_group, setting_name).id, moderators_group.id)

            params[setting_name] = orjson.dumps(
                {
                    "new": marketing_group.id,
                }
            ).decode()
            result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)

            if setting_name == "can_mention_group":
                self.assert_json_success(result)
                support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
                self.assertEqual(getattr(support_group, setting_name).id, marketing_group.id)
            else:
                self.assert_json_error(result, f"'{setting_name}' must be a system user group.")

    def test_update_user_group_permission_settings(self) -> None:
        hamlet = self.example_user("hamlet")
        check_add_user_group(hamlet.realm, "support", [hamlet], acting_user=None)
        check_add_user_group(hamlet.realm, "marketing", [hamlet], acting_user=None)

        for setting_name in NamedUserGroup.GROUP_PERMISSION_SETTINGS:
            self.do_test_update_user_group_permission_settings(setting_name)

    def test_user_group_update_to_already_existing_name(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        realm = get_realm("zulip")
        support_user_group = check_add_user_group(realm, "support", [hamlet], acting_user=None)
        marketing_user_group = check_add_user_group(realm, "marketing", [hamlet], acting_user=None)

        params = {
            "name": marketing_user_group.name,
        }
        result = self.client_patch(f"/json/user_groups/{support_user_group.id}", info=params)
        self.assert_json_error(result, f"User group '{marketing_user_group.name}' already exists.")

    def test_update_can_mention_group_setting_with_previous_value_passed(self) -> None:
        hamlet = self.example_user("hamlet")
        support_group = check_add_user_group(hamlet.realm, "support", [hamlet], acting_user=None)
        marketing_group = check_add_user_group(
            hamlet.realm, "marketing", [hamlet], acting_user=None
        )
        everyone_group = NamedUserGroup.objects.get(
            name="role:everyone", realm=hamlet.realm, is_system_group=True
        )
        moderators_group = NamedUserGroup.objects.get(
            name="role:moderators", realm=hamlet.realm, is_system_group=True
        )

        self.assertEqual(marketing_group.can_mention_group.id, everyone_group.id)
        self.login("hamlet")
        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": marketing_group.id,
                    "old": moderators_group.id,
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "'old' value does not match the expected value.")

        othello = self.example_user("othello")
        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": marketing_group.id,
                    "old": {
                        "direct_members": [othello.id],
                        "direct_subgroups": [everyone_group.id],
                    },
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "'old' value does not match the expected value.")

        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": marketing_group.id,
                    "old": everyone_group.id,
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertEqual(support_group.can_mention_group, marketing_group.usergroup_ptr)

        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": {
                        "direct_members": [othello.id],
                        "direct_subgroups": [moderators_group.id],
                    },
                    "old": {"direct_members": [], "direct_subgroups": [marketing_group.id]},
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertCountEqual(
            list(support_group.can_mention_group.direct_members.all()),
            [othello],
        )
        self.assertCountEqual(
            list(support_group.can_mention_group.direct_subgroups.all()),
            [moderators_group],
        )

        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": {
                        "direct_members": [hamlet.id],
                        "direct_subgroups": [marketing_group.id],
                    },
                    "old": support_group.can_mention_group_id,
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "'old' value does not match the expected value.")

        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": {
                        "direct_members": [hamlet.id],
                        "direct_subgroups": [marketing_group.id],
                    },
                    "old": moderators_group.id,
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "'old' value does not match the expected value.")

        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": {
                        "direct_members": [hamlet.id],
                        "direct_subgroups": [marketing_group.id],
                    },
                    "old": {
                        "direct_members": [othello.id],
                        "direct_subgroups": [moderators_group.id],
                    },
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        self.assertCountEqual(
            list(support_group.can_mention_group.direct_members.all()),
            [hamlet],
        )
        self.assertCountEqual(
            list(support_group.can_mention_group.direct_subgroups.all()),
            [marketing_group],
        )

        # Test error cases for completeness.
        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": {
                        "direct_members": [othello.id],
                        "direct_subgroups": [moderators_group.id],
                    },
                    "old": {
                        "direct_members": [hamlet.id],
                        "direct_subgroups": [1111],
                    },
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "'old' value does not match the expected value.")

        params = {
            "can_mention_group": orjson.dumps(
                {
                    "new": 1111,
                    "old": {
                        "direct_members": [hamlet.id],
                        "direct_subgroups": [marketing_group.id],
                    },
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Invalid user group")

    def test_user_group_delete(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        self.client_post("/json/user_groups/create", info=params)
        user_group = NamedUserGroup.objects.get(name="support")
        # Test success
        self.assertEqual(NamedUserGroup.objects.filter(realm=hamlet.realm).count(), 10)
        self.assertEqual(UserGroupMembership.objects.count(), 45)
        self.assertTrue(NamedUserGroup.objects.filter(id=user_group.id).exists())
        result = self.client_delete(f"/json/user_groups/{user_group.id}")
        self.assert_json_success(result)
        self.assertEqual(NamedUserGroup.objects.filter(realm=hamlet.realm).count(), 9)
        self.assertEqual(UserGroupMembership.objects.count(), 44)
        self.assertFalse(NamedUserGroup.objects.filter(id=user_group.id).exists())
        # Test when invalid user group is supplied; transaction needed for
        # error handling
        with transaction.atomic():
            result = self.client_delete("/json/user_groups/1111")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [self.lear_user("cordelia")], acting_user=None
        )
        result = self.client_delete(f"/json/user_groups/{lear_test_group.id}")
        self.assert_json_error(result, "Invalid user group")

    def test_query_counts(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        realm = hamlet.realm
        self.login_user(hamlet)

        original_users = [
            create_user(
                email=f"original_user{i}@zulip.com",
                password=None,
                realm=realm,
                full_name="full_name",
            )
            for i in range(50)
        ]

        with self.assert_database_query_count(5):
            user_group = create_user_group_in_database(
                name="support",
                members=[hamlet, cordelia, *original_users],
                realm=realm,
                acting_user=hamlet,
            )

        self.assert_user_membership(user_group, [hamlet, cordelia, *original_users])

        new_users = [
            create_user(
                email=f"new_user{i}@zulip.com",
                password=None,
                realm=realm,
                full_name="full_name",
            )
            for i in range(50)
        ]

        new_user_ids = [user.id for user in new_users]

        munge = lambda obj: orjson.dumps(obj).decode()
        params = dict(add=munge(new_user_ids))

        with (
            mock.patch("zerver.views.user_groups.notify_for_user_group_subscription_changes"),
            self.assert_database_query_count(11),
        ):
            result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)

        with self.assert_database_query_count(1):
            all_user_ids = get_user_group_member_ids(user_group, direct_member_only=True)

        self.assert_length(all_user_ids, 102)
        self.assert_user_membership(user_group, [hamlet, cordelia, *new_users, *original_users])

    def test_update_members_of_user_group(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login("hamlet")
        params = {
            "name": "support",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Support team",
        }
        self.client_post("/json/user_groups/create", info=params)
        user_group = NamedUserGroup.objects.get(name="support")
        # Test add members
        self.assert_user_membership(user_group, [hamlet])

        othello = self.example_user("othello")
        # A bot
        webhook_bot = self.example_user("webhook_bot")
        # A deactivated user
        iago = self.example_user("iago")
        do_deactivate_user(iago, acting_user=None)

        params = {"add": orjson.dumps([othello.id]).decode()}
        initial_last_message = self.get_last_message()
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_user_membership(user_group, [hamlet, othello])

        # A notification message is sent for adding to user group.
        self.assertNotEqual(self.get_last_message(), initial_last_message)
        expected_notification = (
            f"{silent_mention_syntax_for_user(hamlet)} added you to the group @_*support*."
        )
        self.assertEqual(self.get_last_message().content, expected_notification)

        # Test adding a member already there.
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_error(result, f"User {othello.id} is already a member of this group")
        self.assert_user_membership(user_group, [hamlet, othello])

        # Test user adding itself, bot and deactivated user to user group.
        desdemona = self.example_user("desdemona")
        self.login_user(desdemona)

        params = {"add": orjson.dumps([desdemona.id, iago.id, webhook_bot.id]).decode()}
        initial_last_message = self.get_last_message()
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_user_membership(user_group, [hamlet, othello, desdemona, iago, webhook_bot])

        # No notification message is sent for adding to user group.
        self.assertEqual(self.get_last_message(), initial_last_message)

        # For normal testing we again log in with hamlet
        self.logout()
        self.login_user(hamlet)
        # Test remove members
        params = {"delete": orjson.dumps([othello.id]).decode()}
        initial_last_message = self.get_last_message()
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_user_membership(user_group, [hamlet, desdemona, iago, webhook_bot])

        # A notification message is sent for removing from user group.
        self.assertNotEqual(self.get_last_message(), initial_last_message)
        expected_notification = (
            f"{silent_mention_syntax_for_user(hamlet)} removed you from the group @_*support*."
        )
        self.assertEqual(self.get_last_message().content, expected_notification)

        # Test remove a member that's already removed
        params = {"delete": orjson.dumps([othello.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_error(result, f"There is no member '{othello.id}' in this user group")
        self.assert_user_membership(user_group, [hamlet, desdemona, iago, webhook_bot])

        # Test user remove itself,bot and deactivated user from user group.
        desdemona = self.example_user("desdemona")
        self.login_user(desdemona)

        params = {"delete": orjson.dumps([desdemona.id, iago.id, webhook_bot.id]).decode()}
        initial_last_message = self.get_last_message()
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_user_membership(user_group, [hamlet])

        # No notification message is sent for removing from user group.
        self.assertEqual(self.get_last_message(), initial_last_message)

        # Test when nothing is provided
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info={})
        msg = 'Nothing to do. Specify at least one of "add" or "delete".'
        self.assert_json_error(result, msg)
        self.assert_user_membership(user_group, [hamlet])

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

        check_add_user_group(
            name=group_name, initial_members=list(support_team), realm=realm, acting_user=None
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

    def test_user_group_edit_policy_for_creating_user_group(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        def check_create_user_group(acting_user: str, error_msg: str | None = None) -> None:
            params = {
                "name": "support",
                "members": orjson.dumps([hamlet.id]).decode(),
                "description": "Support Team",
            }
            result = self.api_post(
                self.example_user(acting_user), "/api/v1/user_groups/create", info=params
            )
            if error_msg is None:
                self.assert_json_success(result)
                # One group already exists in the test database.
                self.assert_length(NamedUserGroup.objects.filter(realm=realm), 10)
            else:
                self.assert_json_error(result, error_msg)

        # Check only admins are allowed to create user group. Admins are allowed even if
        # they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.ADMINS_ONLY,
            acting_user=None,
        )
        check_create_user_group("shiva", "Insufficient permission")
        check_create_user_group("iago")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check moderators are allowed to create user group but not members. Moderators are
        # allowed even if they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.MODERATORS_ONLY,
            acting_user=None,
        )
        check_create_user_group("hamlet", "Insufficient permission")
        check_create_user_group("shiva")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check only members are allowed to create the user group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.MEMBERS_ONLY,
            acting_user=None,
        )
        check_create_user_group("polonius", "Not allowed for guest users")
        check_create_user_group("othello")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check only full members are allowed to create the user group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.FULL_MEMBERS_ONLY,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)

        othello = self.example_user("othello")
        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()

        check_create_user_group("othello", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        check_create_user_group("othello")

    def test_realm_level_policy_for_deleting_user_group(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm

        def check_delete_user_group(acting_user: str, error_msg: str | None = None) -> None:
            user_group = NamedUserGroup.objects.get(name="support")
            with transaction.atomic():
                result = self.api_delete(
                    self.example_user(acting_user), f"/api/v1/user_groups/{user_group.id}"
                )
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_length(NamedUserGroup.objects.filter(realm=realm), 9)
            else:
                self.assert_json_error(result, error_msg)

        self.create_user_group_for_test("support")
        # Check only admins are allowed to delete user group. Admins are allowed even if
        # they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.ADMINS_ONLY,
            acting_user=None,
        )
        check_delete_user_group("shiva", "Insufficient permission")
        check_delete_user_group("iago")

        self.create_user_group_for_test("support")
        # Check moderators are allowed to delete user group but not members. Moderators are
        # allowed even if they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.MODERATORS_ONLY,
            acting_user=None,
        )
        check_delete_user_group("hamlet", "Insufficient permission")
        check_delete_user_group("shiva")

        self.create_user_group_for_test("support")
        # Check only members are allowed to delete the user group and they are allowed to create
        # a user group only if they are a member of that group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.MEMBERS_ONLY,
            acting_user=None,
        )
        check_delete_user_group("polonius", "Not allowed for guest users")
        check_delete_user_group("cordelia", "Insufficient permission")
        check_delete_user_group("othello")

        self.create_user_group_for_test("support")
        # Check only full members are allowed to delete the user group and they are allowed to delete
        # a user group only if they are a member of that group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.FULL_MEMBERS_ONLY,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)

        cordelia = self.example_user("cordelia")
        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()

        othello = self.example_user("othello")
        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()

        check_delete_user_group("cordelia", "Insufficient permission")
        check_delete_user_group("othello", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        check_delete_user_group("othello")

    def test_group_level_setting_for_deleting_user_groups(self) -> None:
        othello = self.example_user("othello")
        realm = othello.realm

        hamlet = self.example_user("hamlet")
        leadership_group = check_add_user_group(
            get_realm("zulip"), "leadership", [hamlet], acting_user=hamlet
        )

        def check_delete_user_group(acting_user: str, error_msg: str | None = None) -> None:
            user_group = NamedUserGroup.objects.get(name="support")
            with transaction.atomic():
                result = self.api_delete(
                    self.example_user(acting_user), f"/api/v1/user_groups/{user_group.id}"
                )
            if error_msg is None:
                self.assert_json_success(result)
            else:
                self.assert_json_error(result, error_msg)

        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_NOBODY,
            acting_user=None,
        )

        support_group = check_add_user_group(
            get_realm("zulip"), "support", [othello], acting_user=None
        )
        # Default value of can_manage_group is "Nobody" system group.
        check_delete_user_group("desdemona", "Insufficient permission")
        check_delete_user_group("othello", "Insufficient permission")

        system_group_dict = get_role_based_system_groups_dict(realm)
        owners_group = system_group_dict[SystemGroups.OWNERS]
        do_change_user_group_permission_setting(
            support_group, "can_manage_group", owners_group, acting_user=None
        )

        check_delete_user_group("iago", "Insufficient permission")
        check_delete_user_group("desdemona")

        check_add_user_group(
            get_realm("zulip"),
            "support",
            [othello],
            "",
            {"can_manage_group": system_group_dict[SystemGroups.MEMBERS]},
            acting_user=None,
        )
        check_delete_user_group("polonius", "Not allowed for guest users")
        check_delete_user_group("cordelia")

        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.example_user("cordelia")], [leadership_group, owners_group]
        )
        check_add_user_group(
            get_realm("zulip"),
            "support",
            [othello],
            "",
            {"can_manage_group": setting_group},
            acting_user=None,
        )
        check_delete_user_group("iago", "Insufficient permission")
        check_delete_user_group("hamlet")

        check_add_user_group(
            get_realm("zulip"),
            "support",
            [othello],
            "",
            {"can_manage_group": setting_group},
            acting_user=None,
        )

        check_delete_user_group("cordelia")
        check_add_user_group(
            get_realm("zulip"),
            "support",
            [othello],
            "",
            {"can_manage_group": setting_group},
            acting_user=None,
        )
        check_delete_user_group("desdemona")

    def test_realm_level_setting_for_updating_user_groups(self) -> None:
        othello = self.example_user("othello")
        self.login("othello")
        params = {
            "name": "support",
            "members": orjson.dumps([othello.id]).decode(),
            "description": "Support team",
        }
        self.client_post("/json/user_groups/create", info=params)
        user_group = NamedUserGroup.objects.get(name="support")

        def check_update_user_group(
            new_name: str,
            new_description: str,
            acting_user: str,
            error_msg: str | None = None,
        ) -> None:
            params = {
                "name": new_name,
                "description": new_description,
            }
            # Ensure that this update request is not a no-op.
            self.assertNotEqual(user_group.name, new_name)
            self.assertNotEqual(user_group.description, new_description)

            result = self.api_patch(
                self.example_user(acting_user), f"/api/v1/user_groups/{user_group.id}", info=params
            )
            if error_msg is None:
                self.assert_json_success(result)
                user_group.refresh_from_db()
                self.assertEqual(user_group.name, new_name)
                self.assertEqual(user_group.description, new_description)
            else:
                self.assert_json_error(result, error_msg)

        realm = othello.realm

        # Check only admins are allowed to update user group. Admins are allowed even if
        # they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.ADMINS_ONLY,
            acting_user=None,
        )
        check_update_user_group("help", "Troubleshooting team", "shiva", "Insufficient permission")
        check_update_user_group("help", "Troubleshooting team", "iago")

        # Check moderators are allowed to update user group but not members. Moderators are
        # allowed even if they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.MODERATORS_ONLY,
            acting_user=None,
        )
        check_update_user_group("support", "Support team", "othello", "Insufficient permission")
        check_update_user_group("support", "Support team", "iago")

        # Check only members are allowed to update the user group and only if belong to the
        # user group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.MEMBERS_ONLY,
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
            realm, "user_group_edit_policy", CommonPolicyEnum.FULL_MEMBERS_ONLY, acting_user=None
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

    def test_group_level_setting_for_updating_user_groups(self) -> None:
        othello = self.example_user("othello")
        iago = self.example_user("iago")
        user_group = check_add_user_group(
            get_realm("zulip"), "support", [othello, iago], acting_user=othello
        )
        hamlet = self.example_user("hamlet")
        leadership_group = check_add_user_group(
            get_realm("zulip"), "leadership", [hamlet], acting_user=hamlet
        )

        def check_update_user_group(
            new_name: str,
            new_description: str,
            acting_user: str,
            error_msg: str | None = None,
        ) -> None:
            params = {
                "name": new_name,
                "description": new_description,
            }
            # Ensure that this update request is not a no-op.
            self.assertNotEqual(user_group.name, new_name)
            self.assertNotEqual(user_group.description, new_description)

            result = self.api_patch(
                self.example_user(acting_user), f"/api/v1/user_groups/{user_group.id}", info=params
            )
            if error_msg is None:
                self.assert_json_success(result)
                user_group.refresh_from_db()
                self.assertEqual(user_group.name, new_name)
                self.assertEqual(user_group.description, new_description)
            else:
                self.assert_json_error(result, error_msg)

        realm = othello.realm

        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_NOBODY,
            acting_user=None,
        )

        # Default value of can_manage_group is "Nobody" system group.
        check_update_user_group("help", "Troubleshooting team", "iago", "Insufficient permission")
        check_update_user_group(
            "help", "Troubleshooting team", "othello", "Insufficient permission"
        )

        system_group_dict = get_role_based_system_groups_dict(realm)
        owners_group = system_group_dict[SystemGroups.OWNERS]
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", owners_group, acting_user=None
        )
        check_update_user_group("help", "Troubleshooting team", "iago", "Insufficient permission")
        check_update_user_group("help", "Troubleshooting team", "desdemona")

        user_group.can_manage_group = system_group_dict[SystemGroups.MEMBERS]
        user_group.save()
        check_update_user_group(
            "support", "Support team", "polonius", "Not allowed for guest users"
        )
        check_update_user_group(
            "support",
            "Support team",
            "cordelia",
        )

        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.example_user("cordelia")], [leadership_group, owners_group]
        )
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", setting_group, acting_user=None
        )
        check_update_user_group("help", "Troubleshooting team", "iago", "Insufficient permission")
        check_update_user_group("help", "Troubleshooting team", "hamlet")
        check_update_user_group(
            "support",
            "Support team",
            "cordelia",
        )
        check_update_user_group("help", "Troubleshooting team", "desdemona")

    def test_realm_level_setting_for_updating_members(self) -> None:
        user_group = self.create_user_group_for_test("support")
        aaron = self.example_user("aaron")
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        def check_adding_members_to_group(acting_user: str, error_msg: str | None = None) -> None:
            params = {"add": orjson.dumps([aaron.id]).decode()}
            self.assert_user_membership(user_group, [othello])
            result = self.api_post(
                self.example_user(acting_user),
                f"/api/v1/user_groups/{user_group.id}/members",
                info=params,
            )
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_user_membership(user_group, [aaron, othello])
            else:
                self.assert_json_error(result, error_msg)

        def check_removing_members_from_group(
            acting_user: str, error_msg: str | None = None
        ) -> None:
            params = {"delete": orjson.dumps([aaron.id]).decode()}
            self.assert_user_membership(user_group, [aaron, othello])
            result = self.api_post(
                self.example_user(acting_user),
                f"/api/v1/user_groups/{user_group.id}/members",
                info=params,
            )
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_user_membership(user_group, [othello])
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")
        # Check only admins are allowed to add/remove users from the group. Admins are allowed even if
        # they are not a member of the group.
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            CommonPolicyEnum.ADMINS_ONLY,
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
            CommonPolicyEnum.MODERATORS_ONLY,
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
            CommonPolicyEnum.MEMBERS_ONLY,
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
            CommonPolicyEnum.FULL_MEMBERS_ONLY,
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

    def test_group_level_setting_for_updating_members(self) -> None:
        othello = self.example_user("othello")
        user_group = check_add_user_group(
            get_realm("zulip"), "support", [othello], acting_user=None
        )
        hamlet = self.example_user("hamlet")
        leadership_group = check_add_user_group(
            get_realm("zulip"), "leadership", [hamlet], acting_user=None
        )
        aaron = self.example_user("aaron")

        def check_adding_members_to_group(acting_user: str, error_msg: str | None = None) -> None:
            params = {"add": orjson.dumps([aaron.id]).decode()}
            self.assert_user_membership(user_group, [othello])
            result = self.api_post(
                self.example_user(acting_user),
                f"/api/v1/user_groups/{user_group.id}/members",
                info=params,
            )
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_user_membership(user_group, [aaron, othello])
            else:
                self.assert_json_error(result, error_msg)

        def check_removing_members_from_group(
            acting_user: str, error_msg: str | None = None
        ) -> None:
            params = {"delete": orjson.dumps([aaron.id]).decode()}
            self.assert_user_membership(user_group, [aaron, othello])
            result = self.api_post(
                self.example_user(acting_user),
                f"/api/v1/user_groups/{user_group.id}/members",
                info=params,
            )
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_user_membership(user_group, [othello])
            else:
                self.assert_json_error(result, error_msg)

        realm = get_realm("zulip")
        do_set_realm_property(
            realm,
            "user_group_edit_policy",
            Realm.POLICY_NOBODY,
            acting_user=None,
        )

        # Default value of can_manage_group is "Nobody system group".
        check_adding_members_to_group("iago", "Insufficient permission")
        check_adding_members_to_group("othello", "Insufficient permission")

        # Add aaron to group so that we can test the removal.
        bulk_add_members_to_user_groups([user_group], [aaron.id], acting_user=None)

        check_removing_members_from_group("iago", "Insufficient permission")
        check_removing_members_from_group("othello", "Insufficient permission")

        # Remove aaron from group to add them again in further tests.
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        system_group_dict = get_role_based_system_groups_dict(realm)
        owners_group = system_group_dict[SystemGroups.OWNERS]
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", owners_group, acting_user=None
        )

        check_adding_members_to_group("iago", "Insufficient permission")
        check_adding_members_to_group("desdemona")

        check_removing_members_from_group("iago", "Insufficient permission")
        check_removing_members_from_group("desdemona")

        members_group = system_group_dict[SystemGroups.MEMBERS]
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", members_group, acting_user=None
        )
        check_adding_members_to_group("polonius", "Not allowed for guest users")
        check_adding_members_to_group("cordelia")

        check_removing_members_from_group("polonius", "Not allowed for guest users")
        check_removing_members_from_group("cordelia")

        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.example_user("cordelia")], [leadership_group, owners_group]
        )
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", setting_group, acting_user=None
        )
        check_adding_members_to_group("iago", "Insufficient permission")
        check_adding_members_to_group("hamlet")

        check_removing_members_from_group("iago", "Insufficient permission")
        check_removing_members_from_group("hamlet")

        check_adding_members_to_group("cordelia")
        check_removing_members_from_group("cordelia")

        check_adding_members_to_group("desdemona")
        check_removing_members_from_group("desdemona")

    def test_editing_system_user_groups(self) -> None:
        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        aaron = self.example_user("aaron")

        user_group = NamedUserGroup.objects.get(
            realm=iago.realm, name=SystemGroups.FULL_MEMBERS, is_system_group=True
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
        full_members_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.FULL_MEMBERS, is_system_group=True
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
        with time_machine.travel((current_time + timedelta(days=3)), tick=False):
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

        leadership_group = check_add_user_group(
            realm, "leadership", [desdemona, iago, hamlet], acting_user=None
        )
        support_group = check_add_user_group(realm, "support", [hamlet, othello], acting_user=None)
        test_group = check_add_user_group(realm, "test", [hamlet], acting_user=None)

        self.login("cordelia")
        # Non-admin and non-moderators who are not a member of group cannot add or remove subgroups.
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Insufficient permission")

        self.login("iago")
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [leadership_group])

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [])

        self.login("shiva")
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [leadership_group])

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [])

        self.login("hamlet")
        # Non-admin and non-moderators who are a member of the user group can add or remove subgroups.
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [leadership_group])

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [])

        # Users need not be part of the subgroup to add or remove it from a user group.
        self.login("othello")
        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [leadership_group])

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [])

        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(
            result,
            f"User group {leadership_group.id} is not a subgroup of this group.",
        )
        self.assert_subgroup_membership(support_group, [])

        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_subgroup_membership(support_group, [leadership_group])

        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(
            result,
            f"User group {leadership_group.id} is already a subgroup of this group.",
        )
        self.assert_subgroup_membership(support_group, [leadership_group])

        self.login("iago")
        params = {"add": orjson.dumps([support_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{leadership_group.id}/subgroups", info=params)
        self.assert_json_error(
            result,
            f"User group {leadership_group.id} is already a subgroup of one of the passed subgroups.",
        )
        self.assert_subgroup_membership(support_group, [leadership_group])

        params = {"add": orjson.dumps([support_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{test_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(test_group, [support_group])

        params = {"add": orjson.dumps([test_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{leadership_group.id}/subgroups", info=params)
        self.assert_json_error(
            result,
            f"User group {leadership_group.id} is already a subgroup of one of the passed subgroups.",
        )
        self.assert_subgroup_membership(test_group, [support_group])

        lear_realm = get_realm("lear")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [self.lear_user("cordelia")], acting_user=None
        )
        result = self.client_post(f"/json/user_groups/{lear_test_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Invalid user group")
        self.assert_subgroup_membership(lear_test_group, [])

        # Invalid subgroup id will raise an error.
        params = {"add": orjson.dumps([leadership_group.id, 1111]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Invalid user group ID: 1111")
        self.assert_subgroup_membership(support_group, [leadership_group])

        # Test when nothing is provided
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info={})
        self.assert_json_error(result, 'Nothing to do. Specify at least one of "add" or "delete".')
        self.assert_subgroup_membership(support_group, [leadership_group])

    def test_get_is_user_group_member_status(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        admins_group = NamedUserGroup.objects.get(
            realm=realm, name=SystemGroups.ADMINISTRATORS, is_system_group=True
        )

        # Invalid user ID.
        result = self.client_get(f"/json/user_groups/{admins_group.id}/members/1111")
        self.assert_json_error(result, "No such user")

        # Invalid user group ID.
        result = self.client_get(f"/json/user_groups/1111/members/{iago.id}")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_cordelia = self.lear_user("cordelia")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [lear_cordelia], acting_user=None
        )
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
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        self.login("iago")

        # Test invalid user group id
        result = self.client_get("/json/user_groups/1111/members")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [self.lear_user("cordelia")], acting_user=None
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
        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm=realm, is_system_group=True
        )
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        self.login("iago")

        # Test invalid user group id
        result = self.client_get("/json/user_groups/1111/subgroups")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [self.lear_user("cordelia")], acting_user=None
        )
        result = self.client_get(f"/json/user_groups/{lear_test_group.id}/subgroups")
        self.assert_json_error(result, "Invalid user group")

        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/subgroups").content
        )
        self.assertEqual(set(result_dict["subgroups"]), {admins_group.id, owners_group.id})

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
        self.assertEqual(set(result_dict["subgroups"]), {admins_group.id, owners_group.id})

        params = {"direct_subgroup_only": orjson.dumps(True).decode()}
        result_dict = orjson.loads(
            self.client_get(
                f"/json/user_groups/{moderators_group.id}/subgroups", info=params
            ).content
        )
        self.assertCountEqual(result_dict["subgroups"], [admins_group.id])

    def test_add_subgroup_from_wrong_realm(self) -> None:
        other_realm = do_create_realm("other", "Other Realm")
        other_user_group = check_add_user_group(other_realm, "user_group", [], acting_user=None)

        realm = get_realm("zulip")
        zulip_group = check_add_user_group(realm, "zulip_test", [], acting_user=None)

        self.login("iago")
        result = self.client_post(
            f"/json/user_groups/{zulip_group.id}/subgroups",
            {"add": orjson.dumps([other_user_group.id]).decode()},
        )
        self.assert_json_error(result, f"Invalid user group ID: {other_user_group.id}")

        # Having a subgroup from another realm is very unlikely because we do
        # not allow cross-realm subgroups being added in the first place. But we
        # test the handling in this scenario for completeness.
        add_subgroups_to_user_group(zulip_group, [other_user_group], acting_user=None)
        result = self.client_post(
            f"/json/user_groups/{zulip_group.id}/subgroups",
            {"delete": orjson.dumps([other_user_group.id]).decode()},
        )
        self.assert_json_error(result, f"Invalid user group ID: {other_user_group.id}")
