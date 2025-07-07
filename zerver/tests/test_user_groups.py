from collections.abc import Iterable
from datetime import datetime, timedelta
from unittest import mock

import orjson
import time_machine
from django.utils.timezone import now as timezone_now

from zerver.actions.create_realm import do_create_realm
from zerver.actions.create_user import do_reactivate_user
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_change_realm_plan_type,
    do_set_realm_property,
)
from zerver.actions.streams import (
    do_change_stream_group_based_setting,
    do_deactivate_stream,
    do_unarchive_stream,
)
from zerver.actions.user_groups import (
    add_subgroups_to_user_group,
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    check_add_user_group,
    create_user_group_in_database,
    do_change_user_group_permission_setting,
    do_deactivate_user_group,
    promote_new_full_members,
    remove_subgroups_from_user_group,
)
from zerver.actions.users import do_deactivate_user
from zerver.lib.create_user import create_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.streams import ensure_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_usermessage
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.types import UserGroupMembersData, UserGroupMembersDict
from zerver.lib.user_groups import (
    check_user_has_permission_by_role,
    get_direct_user_groups,
    get_recursive_group_members,
    get_recursive_group_members_union_for_groups,
    get_recursive_membership_groups,
    get_recursive_strict_subgroups,
    get_recursive_subgroups,
    get_recursive_subgroups_union_for_groups,
    get_recursive_supergroups_union_for_groups,
    get_role_based_system_groups_dict,
    get_subgroup_ids,
    get_system_user_group_by_name,
    get_user_group_member_ids,
    has_user_group_access_for_subgroup,
    is_any_user_in_group,
    is_user_in_group,
    user_groups_in_realm_serialized,
)
from zerver.models import (
    GroupGroupMembership,
    NamedUserGroup,
    Realm,
    Stream,
    UserGroup,
    UserGroupMembership,
    UserProfile,
)
from zerver.models.groups import SystemGroups, get_realm_system_groups_name_dict
from zerver.models.realms import get_realm


class UserGroupTestCase(ZulipTestCase):
    def assert_user_membership(
        self, user_group: NamedUserGroup, members: Iterable[UserProfile]
    ) -> None:
        user_ids = get_user_group_member_ids(user_group, direct_member_only=True)
        self.assertSetEqual(set(user_ids), {member.id for member in members})

    def assert_member_not_in_group(self, user_group: NamedUserGroup, member: UserProfile) -> None:
        user_ids = get_user_group_member_ids(user_group, direct_member_only=True)
        self.assertNotIn(member.id, user_ids)

    def assert_subgroup_membership(
        self, user_group: NamedUserGroup, members: Iterable[UserGroup]
    ) -> None:
        subgroup_ids = get_subgroup_ids(user_group, direct_subgroup_only=True)
        self.assertSetEqual(set(subgroup_ids), {member.id for member in members})

    def create_user_group_for_test(
        self, group_name: str, acting_user: UserProfile
    ) -> NamedUserGroup:
        members = [self.example_user("othello")]
        return check_add_user_group(
            get_realm("zulip"), group_name, members, acting_user=acting_user
        )

    def test_user_groups_in_realm_serialized(self) -> None:
        def convert_date_created_to_timestamp(date_created: datetime | None) -> int | None:
            return datetime_to_timestamp(date_created) if date_created is not None else None

        realm = get_realm("zulip")
        user = self.example_user("iago")
        user_group = NamedUserGroup.objects.filter(realm=realm).first()
        assert user_group is not None
        empty_user_group = check_add_user_group(realm, "newgroup", [], acting_user=user)
        do_deactivate_user(self.example_user("hamlet"), acting_user=None)

        user_groups = user_groups_in_realm_serialized(
            realm, include_deactivated_groups=False
        ).api_groups
        self.assert_length(user_groups, 10)
        self.assertEqual(user_groups[0]["id"], user_group.id)
        self.assertEqual(user_groups[0]["creator_id"], user_group.creator_id)
        self.assertEqual(
            user_groups[0]["date_created"],
            convert_date_created_to_timestamp(user_group.date_created),
        )
        self.assertEqual(user_groups[0]["name"], SystemGroups.NOBODY)
        self.assertEqual(user_groups[0]["description"], "Nobody")
        self.assertEqual(user_groups[0]["members"], [])
        self.assertEqual(user_groups[0]["direct_subgroup_ids"], [])
        self.assertEqual(user_groups[0]["can_manage_group"], user_group.id)
        self.assertEqual(user_groups[0]["can_mention_group"], user_group.id)
        self.assertFalse(user_groups[0]["deactivated"])

        owners_system_group = NamedUserGroup.objects.get(name=SystemGroups.OWNERS, realm=realm)
        membership = UserGroupMembership.objects.filter(user_group=owners_system_group).values_list(
            "user_profile_id", flat=True
        )
        self.assertEqual(user_groups[1]["id"], owners_system_group.id)
        self.assertEqual(user_groups[1]["creator_id"], owners_system_group.creator_id)
        self.assertEqual(
            user_groups[1]["date_created"],
            convert_date_created_to_timestamp(owners_system_group.date_created),
        )
        self.assertEqual(user_groups[1]["name"], SystemGroups.OWNERS)
        self.assertEqual(user_groups[1]["description"], "Owners of this organization")
        self.assertEqual(set(user_groups[1]["members"]), set(membership))
        self.assertEqual(user_groups[1]["direct_subgroup_ids"], [])
        self.assertEqual(user_groups[1]["can_manage_group"], user_group.id)
        self.assertEqual(user_groups[1]["can_mention_group"], user_group.id)
        self.assertFalse(user_groups[0]["deactivated"])

        admins_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm
        )
        self.assertEqual(user_groups[2]["id"], admins_system_group.id)
        # Check that owners system group is present in "direct_subgroup_ids"
        self.assertEqual(user_groups[2]["direct_subgroup_ids"], [owners_system_group.id])

        self.assertEqual(user_groups[8]["name"], "hamletcharacters")
        # Test deactivated user is not included in the members list.
        self.assertEqual(user_groups[8]["members"], [self.example_user("cordelia").id])

        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        self.assertEqual(user_groups[9]["id"], empty_user_group.id)
        self.assertEqual(user_groups[9]["creator_id"], empty_user_group.creator_id)
        self.assertEqual(
            user_groups[9]["date_created"],
            convert_date_created_to_timestamp(empty_user_group.date_created),
        )
        self.assertEqual(user_groups[9]["name"], "newgroup")
        self.assertEqual(user_groups[9]["description"], "")
        self.assertEqual(user_groups[9]["members"], [])
        self.assertEqual(
            user_groups[9]["can_manage_group"],
            UserGroupMembersDict(direct_members=[11], direct_subgroups=[]),
        )
        self.assertEqual(user_groups[9]["can_mention_group"], everyone_group.id)
        self.assertFalse(user_groups[0]["deactivated"])

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
            acting_user=self.example_user("desdemona"),
        )
        user_groups = user_groups_in_realm_serialized(
            realm, include_deactivated_groups=False
        ).api_groups
        self.assertEqual(user_groups[10]["id"], new_user_group.id)
        self.assertEqual(user_groups[10]["creator_id"], new_user_group.creator_id)
        self.assertEqual(
            user_groups[10]["date_created"],
            convert_date_created_to_timestamp(new_user_group.date_created),
        )
        self.assertEqual(user_groups[10]["name"], "newgroup2")
        self.assertEqual(user_groups[10]["description"], "")
        self.assertEqual(user_groups[10]["members"], [othello.id])

        assert not isinstance(user_groups[10]["can_manage_group"], int)
        self.assertEqual(user_groups[10]["can_manage_group"]["direct_members"], [othello.id])
        self.assertCountEqual(
            user_groups[10]["can_manage_group"]["direct_subgroups"],
            [admins_system_group.id, hamletcharacters_group.id],
        )

        assert not isinstance(user_groups[10]["can_mention_group"], int)
        self.assertEqual(user_groups[10]["can_mention_group"]["direct_members"], [othello.id])
        self.assertCountEqual(
            user_groups[10]["can_mention_group"]["direct_subgroups"],
            [admins_system_group.id, hamletcharacters_group.id],
        )
        self.assertFalse(user_groups[0]["deactivated"])

        hamlet = self.example_user("hamlet")
        another_new_group = check_add_user_group(realm, "newgroup3", [hamlet], acting_user=hamlet)
        add_subgroups_to_user_group(
            new_user_group, [another_new_group, owners_system_group], acting_user=None
        )
        do_deactivate_user_group(another_new_group, acting_user=None)
        user_groups = user_groups_in_realm_serialized(
            realm, include_deactivated_groups=True
        ).api_groups
        self.assert_length(user_groups, 12)
        self.assertEqual(user_groups[10]["id"], new_user_group.id)
        self.assertEqual(user_groups[10]["name"], "newgroup2")
        self.assertFalse(user_groups[10]["deactivated"])
        self.assertCountEqual(
            user_groups[10]["direct_subgroup_ids"], [another_new_group.id, owners_system_group.id]
        )
        self.assertEqual(user_groups[11]["id"], another_new_group.id)
        self.assertEqual(user_groups[11]["name"], "newgroup3")
        self.assertTrue(user_groups[11]["deactivated"])

        do_change_realm_permission_group_setting(
            realm, "create_multiuse_invite_group", hamletcharacters_group, acting_user=None
        )
        cordelia = self.example_user("cordelia")
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [cordelia], [owners_system_group]
        )
        do_change_realm_permission_group_setting(
            realm, "can_create_public_channel_group", setting_group, acting_user=None
        )
        realm_user_groups = user_groups_in_realm_serialized(
            realm, include_deactivated_groups=False, fetch_anonymous_group_membership=True
        )
        named_user_groups = realm_user_groups.api_groups
        self.assert_length(named_user_groups, 11)
        self.assertEqual(named_user_groups[10]["id"], new_user_group.id)
        self.assertEqual(named_user_groups[10]["name"], "newgroup2")
        self.assertFalse(named_user_groups[10]["deactivated"])
        self.assertCountEqual(
            named_user_groups[10]["direct_subgroup_ids"],
            [another_new_group.id, owners_system_group.id],
        )

        system_groups_dict = realm_user_groups.system_groups_name_dict
        self.assertEqual(system_groups_dict[user_group.id], SystemGroups.NOBODY)
        self.assertEqual(system_groups_dict[owners_system_group.id], SystemGroups.OWNERS)
        self.assertEqual(system_groups_dict[admins_system_group.id], SystemGroups.ADMINISTRATORS)
        self.assertEqual(system_groups_dict[everyone_group.id], SystemGroups.EVERYONE)

        anonymous_group_membership = realm_user_groups.anonymous_group_membership
        self.assertIn(realm.can_create_public_channel_group_id, anonymous_group_membership)
        self.assertEqual(
            anonymous_group_membership[realm.can_create_public_channel_group_id],
            UserGroupMembersDict(
                direct_members=[cordelia.id], direct_subgroups=[owners_system_group.id]
            ),
        )
        self.assertNotIn(realm.create_multiuse_invite_group_id, anonymous_group_membership)

    def test_get_direct_user_groups(self) -> None:
        othello = self.example_user("othello")
        self.create_user_group_for_test("support", acting_user=self.example_user("desdemona"))
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
        aaron = self.example_user("aaron")
        prospero = self.example_user("prospero")

        leadership_group = check_add_user_group(
            realm, "Leadership", [desdemona], acting_user=desdemona
        )

        staff_group = check_add_user_group(realm, "Staff", [iago], acting_user=iago)
        GroupGroupMembership.objects.create(supergroup=staff_group, subgroup=leadership_group)

        manager_group = check_add_user_group(
            realm, "Managers", [aaron, prospero], acting_user=aaron
        )
        GroupGroupMembership.objects.create(supergroup=manager_group, subgroup=leadership_group)

        everyone_group = check_add_user_group(realm, "Everyone", [shiva], acting_user=shiva)
        GroupGroupMembership.objects.create(supergroup=everyone_group, subgroup=staff_group)
        GroupGroupMembership.objects.create(supergroup=everyone_group, subgroup=manager_group)

        subgroup_for_anonymous_supergroup = check_add_user_group(
            realm, "subgroup_for_anonymous_supergroup", [iago], acting_user=iago
        )
        anonymous_supergroup = check_add_user_group(
            realm, "anonymous_supergroup", [iago], acting_user=iago
        )
        GroupGroupMembership.objects.create(
            supergroup=anonymous_supergroup, subgroup=subgroup_for_anonymous_supergroup
        )

        self.assertCountEqual(
            list(get_recursive_subgroups(leadership_group.id)), [leadership_group.usergroup_ptr]
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(staff_group.id)),
            [leadership_group.usergroup_ptr, staff_group.usergroup_ptr],
        )
        self.assertCountEqual(
            list(get_recursive_subgroups(everyone_group.id)),
            [
                leadership_group.usergroup_ptr,
                staff_group.usergroup_ptr,
                everyone_group.usergroup_ptr,
                manager_group.usergroup_ptr,
            ],
        )

        self.assertCountEqual(
            list(get_recursive_subgroups_union_for_groups([staff_group.id, manager_group.id])),
            [
                leadership_group.usergroup_ptr,
                staff_group.usergroup_ptr,
                manager_group.usergroup_ptr,
            ],
        )

        with self.assert_database_query_count(1):
            recursive_supergroups_union_for_groups = list(
                get_recursive_supergroups_union_for_groups(
                    [leadership_group.id, subgroup_for_anonymous_supergroup.id]
                )
            )
        self.assertCountEqual(
            recursive_supergroups_union_for_groups,
            [
                leadership_group.usergroup_ptr,
                everyone_group.usergroup_ptr,
                staff_group.usergroup_ptr,
                manager_group.usergroup_ptr,
                subgroup_for_anonymous_supergroup.usergroup_ptr,
                anonymous_supergroup.usergroup_ptr,
            ],
        )

        self.assertCountEqual(list(get_recursive_strict_subgroups(leadership_group)), [])
        self.assertCountEqual(list(get_recursive_strict_subgroups(staff_group)), [leadership_group])
        self.assertCountEqual(
            list(get_recursive_strict_subgroups(everyone_group)),
            [leadership_group, staff_group, manager_group],
        )

        self.assertCountEqual(list(get_recursive_group_members(leadership_group.id)), [desdemona])
        self.assertCountEqual(list(get_recursive_group_members(staff_group.id)), [desdemona, iago])
        self.assertCountEqual(
            list(get_recursive_group_members(everyone_group.id)),
            [desdemona, iago, shiva, aaron, prospero],
        )

        self.assertCountEqual(
            list(get_recursive_group_members_union_for_groups([staff_group.id, manager_group.id])),
            [iago, desdemona, aaron, prospero],
        )
        self.assertCountEqual(
            list(
                get_recursive_group_members_union_for_groups([leadership_group.id, staff_group.id])
            ),
            [desdemona, iago],
        )

        self.assertIn(leadership_group.usergroup_ptr, get_recursive_membership_groups(desdemona))
        self.assertIn(staff_group.usergroup_ptr, get_recursive_membership_groups(desdemona))
        self.assertIn(everyone_group.usergroup_ptr, get_recursive_membership_groups(desdemona))
        self.assertIn(manager_group.usergroup_ptr, get_recursive_membership_groups(desdemona))

        self.assertIn(staff_group.usergroup_ptr, get_recursive_membership_groups(iago))
        self.assertIn(everyone_group.usergroup_ptr, get_recursive_membership_groups(iago))
        self.assertNotIn(manager_group.usergroup_ptr, get_recursive_membership_groups(iago))

        self.assertIn(everyone_group.usergroup_ptr, get_recursive_membership_groups(shiva))

        do_deactivate_user(iago, acting_user=None)
        self.assertCountEqual(list(get_recursive_group_members(staff_group.id)), [desdemona])
        self.assertCountEqual(
            list(get_recursive_group_members(everyone_group.id)),
            [desdemona, shiva, aaron, prospero],
        )

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

        self.assertTrue(is_user_in_group(moderators_group.id, shiva))

        # Iago is member of a subgroup of moderators group.
        self.assertTrue(is_user_in_group(moderators_group.id, iago))
        self.assertFalse(is_user_in_group(moderators_group.id, iago, direct_member_only=True))
        self.assertTrue(is_user_in_group(administrators_group.id, iago, direct_member_only=True))

        self.assertFalse(is_user_in_group(moderators_group.id, hamlet))
        self.assertFalse(is_user_in_group(moderators_group.id, hamlet, direct_member_only=True))

        do_deactivate_user(iago, acting_user=None)
        self.assertFalse(is_user_in_group(moderators_group.id, iago))
        self.assertFalse(is_user_in_group(administrators_group.id, iago, direct_member_only=True))

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

        self.assertTrue(is_any_user_in_group(moderators_group.id, [shiva, hamlet, polonius]))

        # Iago is member of a subgroup of moderators group.
        self.assertTrue(is_any_user_in_group(moderators_group.id, [iago, hamlet, polonius]))
        self.assertFalse(
            is_any_user_in_group(
                moderators_group.id, [iago, hamlet, polonius], direct_member_only=True
            )
        )
        self.assertTrue(
            is_any_user_in_group(
                administrators_group.id, [iago, shiva, hamlet], direct_member_only=True
            )
        )

        self.assertFalse(is_any_user_in_group(moderators_group.id, [hamlet, polonius]))
        self.assertFalse(
            is_any_user_in_group(moderators_group.id, [hamlet], direct_member_only=True)
        )

    def test_has_user_group_access_for_subgroup(self) -> None:
        iago = self.example_user("iago")
        zulip_realm = get_realm("zulip")
        zulip_group = check_add_user_group(zulip_realm, "zulip", [], acting_user=iago)
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=zulip_realm, is_system_group=True
        )

        lear_realm = get_realm("lear")
        lear_group = check_add_user_group(lear_realm, "test", [], acting_user=iago)

        self.assertFalse(has_user_group_access_for_subgroup(lear_group, iago))
        self.assertTrue(has_user_group_access_for_subgroup(zulip_group, iago))
        self.assertTrue(has_user_group_access_for_subgroup(moderators_group, iago))

    def test_get_system_user_group_by_name(self) -> None:
        realm = get_realm("zulip")
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )

        self.assertEqual(
            get_system_user_group_by_name(SystemGroups.MODERATORS, realm.id), moderators_group
        )

        with self.assertRaisesRegex(JsonableError, "Invalid system group name."):
            get_system_user_group_by_name("hamletcharacters", realm.id)

    def test_update_user_group_members_noop_case(self) -> None:
        hamlet = self.example_user("hamlet")
        test_group = check_add_user_group(
            hamlet.realm,
            "test_group",
            [self.example_user("othello")],
            "Test group",
            acting_user=self.example_user("othello"),
        )
        # These functions should not do anything if any of the list
        # arguments is empty.
        with self.capture_send_event_calls(expected_num_events=0):
            bulk_add_members_to_user_groups([], [hamlet.id], acting_user=None)
            bulk_add_members_to_user_groups([test_group], [], acting_user=None)
            bulk_remove_members_from_user_groups([], [hamlet.id], acting_user=None)
            bulk_remove_members_from_user_groups([test_group], [], acting_user=None)
            add_subgroups_to_user_group(test_group, [], acting_user=None)
            remove_subgroups_from_user_group(test_group, [], acting_user=None)

    def test_check_user_has_permission_by_role(self) -> None:
        realm = get_realm("zulip")
        system_groups_name_dict = get_realm_system_groups_name_dict(realm.id)

        desdemona = self.example_user("desdemona")
        iago = self.example_user("iago")
        shiva = self.example_user("shiva")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        polonius = self.example_user("polonius")

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        self.assertFalse(
            check_user_has_permission_by_role(desdemona, nobody_group.id, system_groups_name_dict)
        )

        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm=realm, is_system_group=True
        )
        self.assertFalse(
            check_user_has_permission_by_role(iago, owners_group.id, system_groups_name_dict)
        )
        self.assertTrue(
            check_user_has_permission_by_role(desdemona, owners_group.id, system_groups_name_dict)
        )

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        self.assertFalse(
            check_user_has_permission_by_role(shiva, admins_group.id, system_groups_name_dict)
        )
        self.assertTrue(
            check_user_has_permission_by_role(iago, admins_group.id, system_groups_name_dict)
        )
        self.assertTrue(
            check_user_has_permission_by_role(desdemona, admins_group.id, system_groups_name_dict)
        )

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        self.assertFalse(
            check_user_has_permission_by_role(hamlet, moderators_group.id, system_groups_name_dict)
        )
        self.assertTrue(
            check_user_has_permission_by_role(shiva, moderators_group.id, system_groups_name_dict)
        )
        self.assertTrue(
            check_user_has_permission_by_role(iago, moderators_group.id, system_groups_name_dict)
        )

        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        self.assertFalse(
            check_user_has_permission_by_role(polonius, members_group.id, system_groups_name_dict)
        )
        self.assertTrue(
            check_user_has_permission_by_role(hamlet, members_group.id, system_groups_name_dict)
        )

        full_members_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm=realm, is_system_group=True
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        hamlet.refresh_from_db()
        shiva.refresh_from_db()
        othello.refresh_from_db()
        polonius.refresh_from_db()

        hamlet.date_joined = timezone_now() - timedelta(days=9)
        hamlet.save()

        shiva.date_joined = timezone_now() - timedelta(days=9)
        shiva.save()

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()

        polonius.date_joined = timezone_now() - timedelta(days=11)
        polonius.save()

        self.assertFalse(
            check_user_has_permission_by_role(
                polonius, full_members_group.id, system_groups_name_dict
            )
        )
        self.assertFalse(
            check_user_has_permission_by_role(
                hamlet, full_members_group.id, system_groups_name_dict
            )
        )
        self.assertTrue(
            check_user_has_permission_by_role(
                othello, full_members_group.id, system_groups_name_dict
            )
        )
        self.assertTrue(
            check_user_has_permission_by_role(shiva, full_members_group.id, system_groups_name_dict)
        )

        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=realm, is_system_group=True
        )
        self.assertTrue(
            check_user_has_permission_by_role(polonius, everyone_group.id, system_groups_name_dict)
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

        # User groups should not be allowed to be created on limited plans.
        original_plan_type = hamlet.realm.plan_type
        do_change_realm_plan_type(hamlet.realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Available on Zulip Cloud Standard. Upgrade to access.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)
        do_change_realm_plan_type(hamlet.realm, original_plan_type, acting_user=None)

        # Check default value of settings.
        everyone_system_group = NamedUserGroup.objects.get(
            name="role:everyone", realm=hamlet.realm, is_system_group=True
        )
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        self.assertCountEqual(support_group.can_manage_group.direct_members.all(), [hamlet])
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

        # Test we cannot create group with name longer than allowed length.
        params = {
            "name": "a" * (NamedUserGroup.MAX_NAME_LENGTH + 1),
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Test group",
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group name cannot exceed 100 characters.")
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 10)

        # Test empty group name.
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

    def test_creating_groups_with_subgroups(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        subgroup = check_add_user_group(realm, "support", [hamlet], acting_user=hamlet)
        self.login("desdemona")

        othello = self.example_user("othello")
        params = {
            "name": "Troubleshooting",
            "members": orjson.dumps([othello.id]).decode(),
            "description": "Troubleshooting team",
            "subgroups": orjson.dumps([subgroup.id]).decode(),
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        self.assert_length(NamedUserGroup.objects.filter(realm=hamlet.realm), 11)
        user_group = NamedUserGroup.objects.get(name="Troubleshooting", realm=hamlet.realm)
        self.assert_subgroup_membership(user_group, [subgroup])

        # User can add subgroups to a group while creating it even if
        # settings are set to not allow adding subgroups after creating
        # the group.
        self.login("othello")
        self.assertEqual(realm.can_manage_all_groups.named_user_group.name, SystemGroups.OWNERS)

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        params = {
            "name": "Backend",
            "members": orjson.dumps([othello.id]).decode(),
            "description": "Backend team",
            "subgroups": orjson.dumps([subgroup.id]).decode(),
            "can_manage_group": orjson.dumps(admins_group.id).decode(),
            "can_add_members_group": orjson.dumps(admins_group.id).decode(),
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        user_group = NamedUserGroup.objects.get(name="Troubleshooting", realm=realm)
        self.assert_subgroup_membership(user_group, [subgroup])

    def do_test_set_group_setting_during_user_group_creation(self, setting_name: str) -> None:
        self.login("hamlet")
        hamlet = self.example_user("hamlet")
        # Delete all existing user groups except the hamletcharacters group
        NamedUserGroup.objects.exclude(name="hamletcharacters").filter(
            is_system_group=False
        ).delete()

        leadership_group = check_add_user_group(
            hamlet.realm, "leadership", [hamlet], acting_user=hamlet
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

        params = {
            "name": "devops",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Devops team",
        }
        params[setting_name] = orjson.dumps(
            {
                "direct_members": [],
                "direct_subgroups": [],
            }
        ).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_success(result)
        devops_group = NamedUserGroup.objects.get(name="devops", realm=hamlet.realm)
        # We do not create a new UserGroup object in such case.
        self.assertEqual(getattr(devops_group, setting_name).id, nobody_group.id)

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

        self.assert_json_success(result)
        frontend_group = NamedUserGroup.objects.get(name="frontend-team", realm=hamlet.realm)
        self.assertEqual(getattr(frontend_group, setting_name), owners_group.usergroup_ptr)

        params = {
            "name": "frontend",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Frontend team",
        }
        params[setting_name] = orjson.dumps(123456).decode()
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
                "direct_subgroups": [123456, moderators_group.id],
            }
        ).decode()
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "Invalid user group ID: 123456")

        # Test can_mention_group cannot be set to a deactivated group.
        do_deactivate_user_group(leadership_group, acting_user=None)
        params = {
            "name": "social",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Social team",
            "can_mention_group": orjson.dumps(leadership_group.id).decode(),
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group is deactivated.")

        params = {
            "name": "social",
            "members": orjson.dumps([hamlet.id]).decode(),
            "description": "Social team",
            "can_mention_group": orjson.dumps(
                {
                    "direct_members": [othello.id],
                    "direct_subgroups": [leadership_group.id],
                }
            ).decode(),
        }
        result = self.client_post("/json/user_groups/create", info=params)
        self.assert_json_error(result, "User group is deactivated.")

        # Reactivate group to use it in further tests.
        leadership_group.deactivated = False
        leadership_group.save()

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
        result = self.client_patch("/json/user_groups/123456", info=params)
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_cordelia = self.lear_user("cordelia")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [lear_cordelia], acting_user=lear_cordelia
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

        do_deactivate_user_group(user_group, acting_user=None)
        params = {"description": "Troubleshooting and support team"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_success(result)
        user_group = NamedUserGroup.objects.get(id=user_group.id)
        self.assertEqual(user_group.description, "Troubleshooting and support team")

        params = {"name": "Support team"}
        result = self.client_patch(f"/json/user_groups/{user_group.id}", info=params)
        self.assert_json_success(result)
        user_group = NamedUserGroup.objects.get(id=user_group.id)
        self.assertEqual(user_group.name, "Support team")

    def do_test_update_user_group_permission_settings(self, setting_name: str) -> None:
        hamlet = self.example_user("hamlet")

        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        marketing_group = NamedUserGroup.objects.get(name="marketing", realm=hamlet.realm)

        moderators_group = NamedUserGroup.objects.get(
            name="role:moderators", realm=hamlet.realm, is_system_group=True
        )

        self.login("desdemona")
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

        previous_setting_id = getattr(support_group, setting_name).id
        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [],
                    "direct_subgroups": [],
                }
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)
        # Test that the previous UserGroup object is deleted.
        self.assertFalse(UserGroup.objects.filter(id=previous_setting_id).exists())
        self.assertEqual(getattr(support_group, setting_name).id, nobody_group.id)

        params[setting_name] = orjson.dumps({"new": marketing_group.id}).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=hamlet.realm)

        self.assertEqual(getattr(support_group, setting_name).id, marketing_group.id)

        owners_group = NamedUserGroup.objects.get(
            name="role:owners", realm=hamlet.realm, is_system_group=True
        )
        params[setting_name] = orjson.dumps({"new": owners_group.id}).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
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

        params[setting_name] = orjson.dumps({"new": 123456}).decode()
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
                    "direct_subgroups": [123456, marketing_group.id],
                }
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Invalid user group ID: 123456")

        leadership_group = NamedUserGroup.objects.get(realm=hamlet.realm, name="leadership")
        do_deactivate_user_group(leadership_group, acting_user=None)

        params[setting_name] = orjson.dumps({"new": leadership_group.id}).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "User group is deactivated.")

        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [prospero.id],
                    "direct_subgroups": [leadership_group.id],
                }
            }
        ).decode()
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "User group is deactivated.")

        params[setting_name] = orjson.dumps({"new": marketing_group.id}).decode()
        result = self.client_patch(f"/json/user_groups/{leadership_group.id}", info=params)
        self.assert_json_success(result)
        leadership_group = NamedUserGroup.objects.get(realm=hamlet.realm, name="leadership")
        self.assertEqual(getattr(leadership_group, setting_name).id, marketing_group.id)

        leadership_group.deactivated = False
        leadership_group.save()

        # Test updating with value not in the form of GroupSettingChangeRequest
        params[setting_name] = orjson.dumps(support_group.id).decode()
        result = self.client_patch(f"/json/user_groups/{leadership_group.id}", info=params)
        self.assert_json_error(result, f"{setting_name} does not have the expected format")

    def test_update_user_group_permission_settings(self) -> None:
        hamlet = self.example_user("hamlet")
        check_add_user_group(hamlet.realm, "support", [hamlet], acting_user=hamlet)
        check_add_user_group(hamlet.realm, "marketing", [hamlet], acting_user=hamlet)
        check_add_user_group(hamlet.realm, "leadership", [hamlet], acting_user=hamlet)

        for setting_name in NamedUserGroup.GROUP_PERMISSION_SETTINGS:
            self.do_test_update_user_group_permission_settings(setting_name)

    def test_user_group_update_to_already_existing_name(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        realm = get_realm("zulip")
        support_user_group = check_add_user_group(realm, "support", [hamlet], acting_user=hamlet)
        marketing_user_group = check_add_user_group(
            realm, "marketing", [hamlet], acting_user=hamlet
        )

        params = {
            "name": marketing_user_group.name,
        }
        result = self.client_patch(f"/json/user_groups/{support_user_group.id}", info=params)
        self.assert_json_error(result, f"User group '{marketing_user_group.name}' already exists.")

    def test_update_can_mention_group_setting_with_previous_value_passed(self) -> None:
        hamlet = self.example_user("hamlet")
        support_group = check_add_user_group(hamlet.realm, "support", [hamlet], acting_user=hamlet)
        marketing_group = check_add_user_group(
            hamlet.realm, "marketing", [hamlet], acting_user=hamlet
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
                    "new": 123456,
                    "old": {
                        "direct_members": [hamlet.id],
                        "direct_subgroups": [marketing_group.id],
                    },
                }
            ).decode()
        }
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Invalid user group")

    def test_user_group_deactivation(self) -> None:
        support_group = self.create_user_group_for_test(
            "support", acting_user=self.example_user("desdemona")
        )
        leadership_group = self.create_user_group_for_test(
            "leadership", acting_user=self.example_user("othello")
        )
        add_subgroups_to_user_group(support_group, [leadership_group], acting_user=None)
        realm = get_realm("zulip")

        admins_group = NamedUserGroup.objects.get(name=SystemGroups.ADMINISTRATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        self.login("othello")
        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_error(result, "Insufficient permission")

        members_group = NamedUserGroup.objects.get(name=SystemGroups.MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            members_group,
            acting_user=None,
        )

        self.login("othello")
        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertTrue(support_group.deactivated)

        support_group.deactivated = False
        support_group.save()

        # Check admins can deactivate groups even if they are not members
        # of the group.
        self.login("iago")
        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertTrue(support_group.deactivated)

        support_group.deactivated = False
        support_group.save()

        # Check moderators can deactivate groups if they are allowed by
        # can_manage_all_groups even when they are not members of the group.
        admins_group = NamedUserGroup.objects.get(name=SystemGroups.ADMINISTRATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        self.login("shiva")
        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_error(result, "Insufficient permission")

        moderators_group = NamedUserGroup.objects.get(name=SystemGroups.MODERATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            moderators_group,
            acting_user=None,
        )
        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertTrue(support_group.deactivated)

        support_group.deactivated = False
        support_group.save()

        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        do_change_user_group_permission_setting(
            support_group, "can_manage_group", admins_group, acting_user=None
        )

        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_error(result, "Insufficient permission")

        do_change_user_group_permission_setting(
            support_group, "can_manage_group", moderators_group, acting_user=None
        )
        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertTrue(support_group.deactivated)

        support_group.deactivated = False
        support_group.save()

        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.example_user("shiva")], [admins_group]
        )
        do_change_user_group_permission_setting(
            support_group, "can_manage_group", setting_group, acting_user=None
        )

        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertTrue(support_group.deactivated)

        support_group.deactivated = False
        support_group.save()

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_manage_all_groups", moderators_group, acting_user=None
        )
        # Check that group that is subgroup of another group cannot be deactivated.
        result = self.client_post(f"/json/user_groups/{leadership_group.id}/deactivate")
        self.assert_json_error(result, "Cannot deactivate user group in use.")
        data = orjson.loads(result.content)
        self.assertEqual(
            data["objections"], [{"type": "subgroup", "supergroup_ids": [support_group.id]}]
        )

        # If the supergroup is itself deactivated, then subgroup can be deactivated.
        result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
        self.assert_json_success(result)
        result = self.client_post(f"/json/user_groups/{leadership_group.id}/deactivate")
        self.assert_json_success(result)
        leadership_group = NamedUserGroup.objects.get(name="leadership", realm=realm)
        self.assertTrue(leadership_group.deactivated)

        # Check that system groups cannot be deactivated at all.
        self.login("desdemona")
        members_system_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm=realm, is_system_group=True
        )
        result = self.client_post(f"/json/user_groups/{members_system_group.id}/deactivate")
        self.assert_json_error(result, "Insufficient permission")

    def test_user_group_deactivation_with_group_used_for_settings(self) -> None:
        realm = get_realm("zulip")

        hamlet = self.example_user("hamlet")

        support_group = self.create_user_group_for_test(
            "support", acting_user=self.example_user("othello")
        )
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )

        self.login("othello")
        for setting_name in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            anonymous_setting_group = self.create_or_update_anonymous_group_for_setting(
                [hamlet], [moderators_group, support_group]
            )
            do_change_realm_permission_group_setting(
                realm, setting_name, anonymous_setting_group, acting_user=None
            )

            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_error(result, "Cannot deactivate user group in use.")
            data = orjson.loads(result.content)
            self.assertEqual(data["objections"], [{"type": "realm", "settings": [setting_name]}])

            do_change_realm_permission_group_setting(
                realm, setting_name, support_group, acting_user=None
            )

            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_error(result, "Cannot deactivate user group in use.")
            data = orjson.loads(result.content)
            self.assertEqual(data["objections"], [{"type": "realm", "settings": [setting_name]}])

            # Reset the realm setting to one of the system group so this setting
            # does not interfere when testing for another setting.
            do_change_realm_permission_group_setting(
                realm, setting_name, moderators_group, acting_user=None
            )

        stream = ensure_stream(realm, "support", acting_user=None)
        desdemona = self.example_user("desdemona")
        self.login("desdemona")
        for setting_name in Stream.stream_permission_group_settings:
            do_change_stream_group_based_setting(
                stream, setting_name, support_group, acting_user=desdemona
            )

            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_error(result, "Cannot deactivate user group in use.")
            data = orjson.loads(result.content)
            self.assertEqual(
                data["objections"],
                [{"type": "channel", "channel_id": stream.id, "settings": [setting_name]}],
            )

            # Test the group can be deactivated, if the stream which uses
            # this group for a setting is deactivated.
            do_deactivate_stream(stream, acting_user=None)
            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_success(result)
            support_group = NamedUserGroup.objects.get(name="support", realm=realm)
            self.assertTrue(support_group.deactivated)

            support_group.deactivated = False
            support_group.save()

            do_unarchive_stream(stream, "support", acting_user=None)

            anonymous_setting_group_member_dict = UserGroupMembersData(
                direct_members=[hamlet.id], direct_subgroups=[moderators_group.id, support_group.id]
            )
            do_change_stream_group_based_setting(
                stream, setting_name, anonymous_setting_group_member_dict, acting_user=desdemona
            )

            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_error(result, "Cannot deactivate user group in use.")
            data = orjson.loads(result.content)
            self.assertEqual(
                data["objections"],
                [{"type": "channel", "channel_id": stream.id, "settings": [setting_name]}],
            )

            # Test the group can be deactivated, if the stream which uses
            # this group for a setting is deactivated.
            do_deactivate_stream(stream, acting_user=None)
            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_success(result)
            support_group = NamedUserGroup.objects.get(name="support", realm=realm)
            self.assertTrue(support_group.deactivated)

            # Reactivate the group again for further testing.
            support_group.deactivated = False
            support_group.save()

            # Unarchive the stream for the next test
            do_unarchive_stream(stream, "support", acting_user=None)

            # Reset the stream setting to one of the system group so this setting
            # does not interfere when testing for another setting.
            do_change_stream_group_based_setting(
                stream, setting_name, moderators_group, acting_user=desdemona
            )

        leadership_group = self.create_user_group_for_test(
            "leadership", acting_user=self.example_user("othello")
        )
        for setting_name in NamedUserGroup.GROUP_PERMISSION_SETTINGS:
            do_change_user_group_permission_setting(
                leadership_group, setting_name, support_group, acting_user=None
            )

            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_error(result, "Cannot deactivate user group in use.")
            data = orjson.loads(result.content)
            self.assertEqual(
                data["objections"],
                [
                    {
                        "type": "user_group",
                        "group_id": leadership_group.id,
                        "settings": [setting_name],
                    }
                ],
            )

            # Test the group can be deactivated, if the user group which uses
            # this group for a setting is deactivated.
            do_deactivate_user_group(leadership_group, acting_user=None)
            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_success(result)
            support_group = NamedUserGroup.objects.get(name="support", realm=realm)
            self.assertTrue(support_group.deactivated)

            support_group.deactivated = False
            support_group.save()

            leadership_group.deactivated = False
            leadership_group.save()

            anonymous_setting_group = self.create_or_update_anonymous_group_for_setting(
                [hamlet], [moderators_group, support_group]
            )
            do_change_user_group_permission_setting(
                leadership_group, setting_name, anonymous_setting_group, acting_user=None
            )

            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_error(result, "Cannot deactivate user group in use.")
            data = orjson.loads(result.content)
            self.assertEqual(
                data["objections"],
                [
                    {
                        "type": "user_group",
                        "group_id": leadership_group.id,
                        "settings": [setting_name],
                    }
                ],
            )

            # Test the group can be deactivated, if the user group which uses
            # this group for a setting is deactivated.
            do_deactivate_user_group(leadership_group, acting_user=None)
            result = self.client_post(f"/json/user_groups/{support_group.id}/deactivate")
            self.assert_json_success(result)
            support_group = NamedUserGroup.objects.get(name="support", realm=realm)
            self.assertTrue(support_group.deactivated)

            # Reactivate the group again for further testing.
            support_group.deactivated = False
            support_group.save()

            leadership_group.deactivated = False
            leadership_group.save()

            # Reset the group setting to one of the system group so this setting
            # does not interfere when testing for another setting.
            do_change_user_group_permission_setting(
                leadership_group, setting_name, moderators_group, acting_user=None
            )

    def test_user_group_reactivation(self) -> None:
        support_group = self.create_user_group_for_test(
            "support", acting_user=self.example_user("desdemona")
        )
        realm = get_realm("zulip")

        admins_group = NamedUserGroup.objects.get(name=SystemGroups.ADMINISTRATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )

        do_deactivate_user_group(support_group, acting_user=None)
        self.login("othello")
        params = {"deactivated": orjson.dumps(False).decode()}
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Insufficient permission")

        members_group = NamedUserGroup.objects.get(name=SystemGroups.MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            members_group,
            acting_user=None,
        )

        self.login("othello")
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertFalse(support_group.deactivated)

        do_deactivate_user_group(support_group, acting_user=None)

        # Check admins can deactivate groups even if they are not members
        # of the group.
        self.login("iago")
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertFalse(support_group.deactivated)

        do_deactivate_user_group(support_group, acting_user=None)

        # Check moderators can deactivate groups if they are allowed by
        # can_manage_all_groups even when they are not members of the group.
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        self.login("shiva")
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Insufficient permission")

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            moderators_group,
            acting_user=None,
        )
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertFalse(support_group.deactivated)

        do_deactivate_user_group(support_group, acting_user=None)

        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        do_change_user_group_permission_setting(
            support_group, "can_manage_group", admins_group, acting_user=None
        )

        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_error(result, "Insufficient permission")

        do_change_user_group_permission_setting(
            support_group, "can_manage_group", moderators_group, acting_user=None
        )
        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertFalse(support_group.deactivated)

        do_deactivate_user_group(support_group, acting_user=None)

        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.example_user("shiva")], [admins_group]
        )
        do_change_user_group_permission_setting(
            support_group, "can_manage_group", setting_group, acting_user=None
        )

        result = self.client_patch(f"/json/user_groups/{support_group.id}", info=params)
        self.assert_json_success(result)
        support_group = NamedUserGroup.objects.get(name="support", realm=realm)
        self.assertFalse(support_group.deactivated)

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

        with self.assert_database_query_count(9):
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
            self.assert_database_query_count(15),
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
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_error(result, f"Invalid user ID: {iago.id}")

        params = {"add": orjson.dumps([desdemona.id, webhook_bot.id]).decode()}
        initial_last_message = self.get_last_message()
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_user_membership(user_group, [hamlet, othello, desdemona, webhook_bot])

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
        self.assert_user_membership(user_group, [hamlet, desdemona, webhook_bot])

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
        self.assert_user_membership(user_group, [hamlet, desdemona, webhook_bot])

        # Test user remove itself,bot and deactivated user from user group.
        desdemona = self.example_user("desdemona")
        self.login_user(desdemona)

        # Add user to group after reactivation to test removing deactivated user.
        do_reactivate_user(iago, acting_user=None)
        self.client_post(
            f"/json/user_groups/{user_group.id}/members",
            info={"add": orjson.dumps([iago.id]).decode()},
        )
        do_deactivate_user(iago, acting_user=None)

        params = {"delete": orjson.dumps([iago.id, desdemona.id, webhook_bot.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_error(result, f"Invalid user ID: {iago.id}")

        params = {"delete": orjson.dumps([desdemona.id, webhook_bot.id]).decode()}
        initial_last_message = self.get_last_message()
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_user_membership(user_group, [hamlet])

        # No notification message is sent for removing from user group.
        self.assertEqual(self.get_last_message(), initial_last_message)

        # Test adding and removing subgroups.
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=hamlet.realm, is_system_group=True
        )
        cordelia = self.example_user("cordelia")
        subgroup = check_add_user_group(
            hamlet.realm, "leadership", [cordelia], acting_user=cordelia
        )
        params = {"add_subgroups": orjson.dumps([subgroup.id, admins_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(user_group, [subgroup, admins_group])

        params = {"delete_subgroups": orjson.dumps([admins_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(user_group, [subgroup])

        # Test when nothing is provided
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info={})
        msg = 'Nothing to do. Specify at least one of "add", "delete", "add_subgroups" or "delete_subgroups".'
        self.assert_json_error(result, msg)
        self.assert_user_membership(user_group, [hamlet])

        # Test adding or removing members from a deactivated group.
        do_deactivate_user_group(user_group, acting_user=None)

        params = {"delete": orjson.dumps([hamlet.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
        self.assert_member_not_in_group(user_group, hamlet)

        params = {"add": orjson.dumps([hamlet.id]).decode()}
        result = self.client_post(f"/json/user_groups/{user_group.id}/members", info=params)
        self.assert_json_success(result)
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
            name=group_name, initial_members=list(support_team), realm=realm, acting_user=hamlet
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

    def test_can_create_groups_for_creating_user_group(self) -> None:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm
        aaron = self.example_user("aaron")
        aaron_group = check_add_user_group(
            get_realm("zulip"), "aaron_group", [aaron], acting_user=aaron
        )

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
                # One group already exists in the test database and we've created one
                # more for testing just before running this function.
                self.assert_length(NamedUserGroup.objects.filter(realm=realm), 11)
            else:
                self.assert_json_error(result, error_msg)

        # Check only admins are allowed to create user group. Admins are allowed even if
        # they are not a member of the group.
        admins_group = NamedUserGroup.objects.get(name=SystemGroups.ADMINISTRATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_create_groups",
            admins_group,
            acting_user=None,
        )
        check_create_user_group("shiva", "Insufficient permission")
        check_create_user_group("iago")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check moderators are allowed to create user group but not members. Moderators are
        # allowed even if they are not a member of the group.
        moderators_group = NamedUserGroup.objects.get(name=SystemGroups.MODERATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_create_groups",
            moderators_group,
            acting_user=None,
        )
        check_create_user_group("hamlet", "Insufficient permission")
        check_create_user_group("shiva")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check if members of a NamedUserGroup are allowed to create user groups.
        do_change_realm_permission_group_setting(
            realm,
            "can_create_groups",
            aaron_group,
            acting_user=None,
        )
        check_create_user_group("shiva", "Insufficient permission")
        check_create_user_group("aaron")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check if members of an anonymous group are allowed to create user groups.
        cordelia = self.example_user("cordelia")
        anonymous_group = self.create_or_update_anonymous_group_for_setting(
            [cordelia], [admins_group, moderators_group]
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_create_groups",
            anonymous_group,
            acting_user=None,
        )
        check_create_user_group("aaron", "Insufficient permission")
        check_create_user_group("cordelia")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()
        check_create_user_group("shiva")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()
        check_create_user_group("iago")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check only members are allowed to create the user group.
        members_group = NamedUserGroup.objects.get(name=SystemGroups.MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_create_groups",
            members_group,
            acting_user=None,
        )
        check_create_user_group("polonius", "Not allowed for guest users")
        check_create_user_group("othello")
        NamedUserGroup.objects.get(name="support", realm=realm).delete()

        # Check only full members are allowed to create the user group.
        full_members_group = NamedUserGroup.objects.get(name=SystemGroups.FULL_MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_create_groups",
            full_members_group,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)

        othello = self.example_user("othello")
        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()

        check_create_user_group("othello", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        promote_new_full_members()
        check_create_user_group("othello")

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
        admins_group = NamedUserGroup.objects.get(name=SystemGroups.ADMINISTRATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        check_update_user_group("help", "Troubleshooting team", "shiva", "Insufficient permission")
        check_update_user_group("help", "Troubleshooting team", "iago")

        # Check moderators are allowed to update user group but not members. Moderators are
        # allowed even if they are not a member of the group.
        moderators_group = NamedUserGroup.objects.get(name=SystemGroups.MODERATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            moderators_group,
            acting_user=None,
        )
        check_update_user_group("support", "Support team", "hamlet", "Insufficient permission")
        check_update_user_group("support1", "Support team - test", "iago")
        check_update_user_group("support", "Support team", "othello")

        # Check only members are allowed to update the user group.
        members_group = NamedUserGroup.objects.get(name=SystemGroups.MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            members_group,
            acting_user=None,
        )
        check_update_user_group(
            "help", "Troubleshooting team", "polonius", "Not allowed for guest users"
        )
        check_update_user_group("help", "Troubleshooting team", "cordelia")

        # Check user who is member of a subgroup of the group being updated
        # can also update the group.
        cordelia = self.example_user("cordelia")
        subgroup = check_add_user_group(realm, "leadership", [cordelia], acting_user=cordelia)
        add_subgroups_to_user_group(user_group, [subgroup], acting_user=None)
        check_update_user_group(
            "support",
            "Support team",
            "cordelia",
        )

        # Check only full members are allowed to update the user group and only if belong to the
        # user group.
        full_members_group = NamedUserGroup.objects.get(name=SystemGroups.FULL_MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            full_members_group,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)
        aaron = self.example_user("aaron")
        aaron.date_joined = timezone_now() - timedelta(days=9)
        aaron.save()

        cordelia = self.example_user("cordelia")
        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        promote_new_full_members()
        check_update_user_group(
            "help",
            "Troubleshooting team",
            "cordelia",
        )
        check_update_user_group("support", "Support team", "aaron", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        promote_new_full_members()
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

        nobody_group = NamedUserGroup.objects.get(name=SystemGroups.NOBODY, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            nobody_group,
            acting_user=None,
        )

        # Default value of can_manage_group is "Nobody" system group.
        check_update_user_group("help", "Troubleshooting team", "iago", "Insufficient permission")
        check_update_user_group("help", "Troubleshooting team", "aaron", "Insufficient permission")

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
        user_group = self.create_user_group_for_test(
            "support", acting_user=self.example_user("desdemona")
        )
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
        # Check only admins are allowed to add/remove users from the group.
        admins_group = NamedUserGroup.objects.get(name=SystemGroups.ADMINISTRATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        check_adding_members_to_group("shiva", "Insufficient permission")
        check_adding_members_to_group("iago")

        check_removing_members_from_group("shiva", "Insufficient permission")
        check_removing_members_from_group("iago")

        # Check moderators are allowed to add/remove users from the group but not members.
        moderators_group = NamedUserGroup.objects.get(name=SystemGroups.MODERATORS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            moderators_group,
            acting_user=None,
        )
        check_adding_members_to_group("cordelia", "Insufficient permission")
        check_adding_members_to_group("shiva")

        check_removing_members_from_group("hamlet", "Insufficient permission")
        check_removing_members_from_group("shiva")

        # Check if members of a NamedUserGroup are allowed to add/remove members.
        othello_group = check_add_user_group(
            get_realm("zulip"), "othello_group", [othello], acting_user=othello
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            othello_group,
            acting_user=None,
        )
        check_adding_members_to_group("shiva", "Insufficient permission")
        check_adding_members_to_group("othello")

        check_removing_members_from_group("shiva", "Insufficient permission")
        check_removing_members_from_group("othello")

        # Check if members of an anonymous group are allowed to add/remove members.
        anonymous_group = self.create_or_update_anonymous_group_for_setting(
            [othello], [admins_group, moderators_group]
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            anonymous_group,
            acting_user=None,
        )

        check_adding_members_to_group("cordelia", "Insufficient permission")
        check_adding_members_to_group("shiva")
        check_removing_members_from_group("hamlet", "Insufficient permission")
        check_removing_members_from_group("shiva")

        check_adding_members_to_group("iago")
        check_removing_members_from_group("iago")

        check_adding_members_to_group("othello")
        check_removing_members_from_group("othello")

        # Check only members are allowed to add/remove users in the group.
        members_group = NamedUserGroup.objects.get(name=SystemGroups.MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            members_group,
            acting_user=None,
        )
        check_adding_members_to_group("polonius", "Not allowed for guest users")

        # User with role member but not part of the target group should
        # be allowed to add members to the group if they are part of
        # `can_manage_all_groups`.
        check_adding_members_to_group("cordelia")
        check_removing_members_from_group("cordelia")

        check_adding_members_to_group("othello")
        check_removing_members_from_group("polonius", "Not allowed for guest users")
        check_removing_members_from_group("othello")

        # Check only full members are allowed to add/remove users in the group.
        full_members_group = NamedUserGroup.objects.get(name=SystemGroups.FULL_MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            full_members_group,
            acting_user=None,
        )
        do_set_realm_property(realm, "waiting_period_threshold", 10, acting_user=None)

        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()
        promote_new_full_members()
        check_adding_members_to_group("cordelia", "Insufficient permission")

        cordelia.date_joined = timezone_now() - timedelta(days=11)
        cordelia.save()
        promote_new_full_members()

        # Full members who are not part of the target group should
        # be allowed to add members to the group if they are part of
        # `can_manage_all_groups`.
        check_adding_members_to_group("cordelia")
        check_removing_members_from_group("cordelia")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        promote_new_full_members()
        check_adding_members_to_group("othello")

        othello.date_joined = timezone_now() - timedelta(days=9)
        othello.save()
        promote_new_full_members()

        check_removing_members_from_group("othello", "Insufficient permission")

        othello.date_joined = timezone_now() - timedelta(days=11)
        othello.save()
        promote_new_full_members()
        check_removing_members_from_group("othello")

    def test_group_level_setting_for_adding_members(self) -> None:
        othello = self.example_user("othello")
        user_group = check_add_user_group(
            get_realm("zulip"), "support", [othello], acting_user=self.example_user("desdemona")
        )
        hamlet = self.example_user("hamlet")
        leadership_group = check_add_user_group(
            get_realm("zulip"), "leadership", [hamlet], acting_user=hamlet
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

        realm = get_realm("zulip")
        nobody_group = NamedUserGroup.objects.get(name=SystemGroups.NOBODY, realm=realm)
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            nobody_group,
            acting_user=None,
        )

        # Default value of can_add_members_group is "group_creator".
        check_adding_members_to_group("iago", "Insufficient permission")
        check_adding_members_to_group("desdemona")
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        # Remove aaron from group to add them again in further tests.
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        # Test setting can_add_members_group to a system group.
        system_group_dict = get_role_based_system_groups_dict(realm)
        owners_group = system_group_dict[SystemGroups.OWNERS]
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", nobody_group, acting_user=None
        )
        do_change_user_group_permission_setting(
            user_group, "can_add_members_group", owners_group, acting_user=None
        )

        check_adding_members_to_group("iago", "Insufficient permission")
        check_adding_members_to_group("desdemona")
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        # Although we can't set this value to everyone via the API,
        # it is a good way here to test whether guest users are allowed
        # to take the action or not.
        everyone_group = system_group_dict[SystemGroups.EVERYONE]
        do_change_user_group_permission_setting(
            user_group, "can_add_members_group", everyone_group, acting_user=None
        )
        check_adding_members_to_group("polonius", "Not allowed for guest users")
        check_adding_members_to_group("cordelia")
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        # Test setting can_add_members_group to an anonymous group with
        # subgroups.
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.example_user("cordelia")], [leadership_group, owners_group]
        )
        do_change_user_group_permission_setting(
            user_group, "can_add_members_group", setting_group, acting_user=None
        )
        check_adding_members_to_group("iago", "Insufficient permission")
        check_adding_members_to_group("hamlet")
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        check_adding_members_to_group("cordelia")
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        check_adding_members_to_group("desdemona")
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

        # If user is part of `can_manage_group`, they need not be part
        # of `can_add_members_group` to add members.
        othello_group = self.create_or_update_anonymous_group_for_setting([othello], [])
        hamlet_group = self.create_or_update_anonymous_group_for_setting([hamlet], [])
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", othello_group, acting_user=None
        )
        do_change_user_group_permission_setting(
            user_group, "can_add_members_group", hamlet_group, acting_user=None
        )
        check_adding_members_to_group("othello")
        bulk_remove_members_from_user_groups([user_group], [aaron.id], acting_user=None)

    def test_group_level_setting_for_removing_members(self) -> None:
        othello = self.example_user("othello")
        aaron = self.example_user("aaron")

        realm = othello.realm
        nobody_group = NamedUserGroup.objects.get(name=SystemGroups.NOBODY, realm=realm)
        user_group = check_add_user_group(
            get_realm("zulip"),
            "support",
            [othello, aaron],
            group_settings_map={"can_manage_group": nobody_group},
            acting_user=self.example_user("desdemona"),
        )
        hamlet = self.example_user("hamlet")
        leadership_group = check_add_user_group(
            get_realm("zulip"), "leadership", [hamlet], acting_user=hamlet
        )

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

        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            nobody_group,
            acting_user=None,
        )

        # By default can_remove_members_group is set to "Nobody" group.
        check_removing_members_from_group("iago", "Insufficient permission")
        check_removing_members_from_group("desdemona", "Insufficient permission")

        # Test setting can_remove_members_group to a system group.
        system_group_dict = get_role_based_system_groups_dict(realm)
        owners_group = system_group_dict[SystemGroups.OWNERS]
        do_change_user_group_permission_setting(
            user_group, "can_remove_members_group", owners_group, acting_user=None
        )

        check_removing_members_from_group("iago", "Insufficient permission")
        check_removing_members_from_group("desdemona")

        # Add aaron to group to remove them again in further tests.
        bulk_add_members_to_user_groups([user_group], [aaron.id], acting_user=None)

        # Although we can't set this value to everyone via the API,
        # it is a good way here to test whether guest users are allowed
        # to take the action or not.
        everyone_group = system_group_dict[SystemGroups.EVERYONE]
        do_change_user_group_permission_setting(
            user_group, "can_remove_members_group", everyone_group, acting_user=None
        )
        check_removing_members_from_group("polonius", "Not allowed for guest users")
        check_removing_members_from_group("cordelia")
        bulk_add_members_to_user_groups([user_group], [aaron.id], acting_user=None)

        # Test setting can_remove_members_group to an anonymous group with
        # subgroups.
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.example_user("cordelia")], [leadership_group, owners_group]
        )
        do_change_user_group_permission_setting(
            user_group, "can_remove_members_group", setting_group, acting_user=None
        )
        check_removing_members_from_group("iago", "Insufficient permission")
        check_removing_members_from_group("hamlet")
        bulk_add_members_to_user_groups([user_group], [aaron.id], acting_user=None)

        check_removing_members_from_group("cordelia")
        bulk_add_members_to_user_groups([user_group], [aaron.id], acting_user=None)

        check_removing_members_from_group("desdemona")
        bulk_add_members_to_user_groups([user_group], [aaron.id], acting_user=None)

        # If user is part of can_manage_group, they need not be part
        # of can_remove_members_group to remove members.
        othello_group = self.create_or_update_anonymous_group_for_setting([othello], [])
        hamlet_group = self.create_or_update_anonymous_group_for_setting([hamlet], [])
        do_change_user_group_permission_setting(
            user_group, "can_manage_group", othello_group, acting_user=None
        )
        do_change_user_group_permission_setting(
            user_group, "can_remove_members_group", hamlet_group, acting_user=None
        )
        check_removing_members_from_group("othello")
        bulk_add_members_to_user_groups([user_group], [aaron.id], acting_user=None)

        check_removing_members_from_group("hamlet")

    def test_adding_yourself_to_group(self) -> None:
        realm = get_realm("zulip")
        othello = self.example_user("othello")
        user_group = check_add_user_group(realm, "support", [othello], acting_user=othello)

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        # Set permissions to manage the group and adding others to group
        # to nobody to test can_join_group in isolation.
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            nobody_group,
            acting_user=None,
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_manage_group",
            nobody_group,
            acting_user=None,
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_add_members_group",
            nobody_group,
            acting_user=None,
        )

        def check_adding_yourself_to_group(acting_user: str, error_msg: str | None = None) -> None:
            user = self.example_user(acting_user)
            self.assert_user_membership(user_group, [othello])

            params = {"add": orjson.dumps([user.id]).decode()}
            result = self.api_post(
                user,
                f"/api/v1/user_groups/{user_group.id}/members",
                info=params,
            )
            if error_msg is not None:
                self.assert_json_error(result, error_msg)
                self.assert_user_membership(user_group, [othello])
            else:
                self.assert_json_success(result)
                self.assert_user_membership(user_group, [othello, user])

                # Remove the added user again for further tests.
                bulk_remove_members_from_user_groups([user_group], [user.id], acting_user=None)

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_join_group",
            admins_group.usergroup_ptr,
            acting_user=None,
        )
        check_adding_yourself_to_group("shiva", "Insufficient permission")
        check_adding_yourself_to_group("iago")
        check_adding_yourself_to_group("desdemona")

        # Test with setting set to a user defined group.
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        leadership_group = check_add_user_group(
            realm, "leadership", [hamlet, cordelia], acting_user=hamlet
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_join_group",
            leadership_group.usergroup_ptr,
            acting_user=None,
        )
        check_adding_yourself_to_group("iago", "Insufficient permission")
        check_adding_yourself_to_group("hamlet")

        # Test with setting set to an anonymous group.
        shiva = self.example_user("shiva")
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [shiva], [leadership_group]
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_join_group",
            setting_group,
            acting_user=None,
        )

        check_adding_yourself_to_group("iago", "Insufficient permission")
        check_adding_yourself_to_group("cordelia")
        check_adding_yourself_to_group("shiva")

        # If user is allowed to add anyone, then they can join themselves
        # even when can_join_group setting does not allow them to do so.
        do_change_user_group_permission_setting(
            user_group,
            "can_join_group",
            nobody_group,
            acting_user=None,
        )
        self.assertEqual(user_group.can_join_group.named_user_group, nobody_group)
        check_adding_yourself_to_group("iago", "Insufficient permission")

        do_change_user_group_permission_setting(
            user_group,
            "can_add_members_group",
            admins_group,
            acting_user=None,
        )
        check_adding_yourself_to_group("iago")

        # If user is allowed to manage the group, then they can join themselves
        # even when can_join_group and can_add_members_group does not allow them.
        do_change_user_group_permission_setting(
            user_group,
            "can_add_members_group",
            nobody_group,
            acting_user=None,
        )
        self.assertEqual(user_group.can_add_members_group.named_user_group, nobody_group)
        check_adding_yourself_to_group("iago", "Insufficient permission")

        do_change_user_group_permission_setting(
            user_group,
            "can_manage_group",
            admins_group,
            acting_user=None,
        )
        check_adding_yourself_to_group("iago")

        do_change_user_group_permission_setting(
            user_group,
            "can_manage_group",
            nobody_group,
            acting_user=None,
        )
        self.assertEqual(realm.can_manage_all_groups.named_user_group, nobody_group)
        check_adding_yourself_to_group("iago", "Insufficient permission")

        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            admins_group,
            acting_user=None,
        )
        check_adding_yourself_to_group("iago")

    def test_leaving_a_group(self) -> None:
        realm = get_realm("zulip")
        othello = self.example_user("othello")
        user_group = check_add_user_group(realm, "support", [othello], acting_user=othello)

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        # Set manage permissions to nobody to test can_leave_group in
        # isolation.
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            nobody_group,
            acting_user=None,
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_manage_group",
            nobody_group,
            acting_user=None,
        )

        def check_leaving_a_group(acting_user: str, error_msg: str | None = None) -> None:
            user = self.example_user(acting_user)
            bulk_add_members_to_user_groups([user_group], [user.id], acting_user=None)

            params = {"delete": orjson.dumps([user.id]).decode()}
            result = self.api_post(
                user,
                f"/api/v1/user_groups/{user_group.id}/members",
                info=params,
            )
            if error_msg is not None:
                self.assert_json_error(result, error_msg)
                self.assert_user_membership(user_group, [user, othello])
                # Remove the user for the next test.
                bulk_remove_members_from_user_groups([user_group], [user.id], acting_user=None)
            else:
                self.assert_json_success(result)
                self.assert_member_not_in_group(user_group, user)

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm=realm, is_system_group=True
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_leave_group",
            admins_group,
            acting_user=None,
        )
        check_leaving_a_group("shiva", "Insufficient permission")
        check_leaving_a_group("iago")
        check_leaving_a_group("desdemona")

        # Test with setting set to a user defined group.
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        leadership_group = check_add_user_group(
            realm, "leadership", [hamlet, cordelia], acting_user=hamlet
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_leave_group",
            leadership_group,
            acting_user=None,
        )
        check_leaving_a_group("iago", "Insufficient permission")
        check_leaving_a_group("hamlet")

        # Test with setting set to an anonymous group.
        shiva = self.example_user("shiva")
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [shiva], [leadership_group]
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_leave_group",
            setting_group,
            acting_user=None,
        )

        check_leaving_a_group("iago", "Insufficient permission")
        check_leaving_a_group("cordelia")
        check_leaving_a_group("shiva")

        # If user is allowed to remove anyone, then they can leave themselves
        # even when can_leave_group setting does not allow them to do so.
        do_change_user_group_permission_setting(
            user_group,
            "can_leave_group",
            nobody_group,
            acting_user=None,
        )
        self.assertEqual(user_group.can_leave_group.named_user_group, nobody_group)
        check_leaving_a_group("iago", "Insufficient permission")

        do_change_user_group_permission_setting(
            user_group,
            "can_remove_members_group",
            admins_group,
            acting_user=None,
        )
        check_leaving_a_group("iago")

        # If user is allowed to manage a group, then they can leave
        # even when can_leave_group does not allow them to do so.
        do_change_user_group_permission_setting(
            user_group,
            "can_leave_group",
            nobody_group,
            acting_user=None,
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_manage_group",
            admins_group,
            acting_user=None,
        )
        check_leaving_a_group("iago")

        # If user is allowed to manage all groups, then they can leave
        # even when can_leave_group does not allow them to do so.
        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm=realm, is_system_group=True
        )
        do_change_user_group_permission_setting(
            user_group,
            "can_manage_group",
            nobody_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            owners_group,
            acting_user=None,
        )
        check_leaving_a_group("desdemona")

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
            realm, "leadership", [desdemona, iago, hamlet], acting_user=desdemona
        )
        support_group = check_add_user_group(
            realm, "support", [hamlet, othello], acting_user=hamlet
        )
        test_group = check_add_user_group(realm, "test", [hamlet], acting_user=hamlet)

        self.login("hamlet")
        # Group creator can add or remove subgroups as they are member of can_manage_group.
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

        self.login("desdemona")
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
        lear_cordelia = self.lear_user("cordelia")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [lear_cordelia], acting_user=lear_cordelia
        )
        result = self.client_post(f"/json/user_groups/{lear_test_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Invalid user group")
        self.assert_subgroup_membership(lear_test_group, [])

        # Invalid subgroup id will raise an error.
        params = {"add": orjson.dumps([leadership_group.id, 123456]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_error(result, "Invalid user group ID: 123456")
        self.assert_subgroup_membership(support_group, [leadership_group])

        # Test when nothing is provided
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info={})
        self.assert_json_error(result, 'Nothing to do. Specify at least one of "add" or "delete".')
        self.assert_subgroup_membership(support_group, [leadership_group])

        # Do not have support group as subgroup of any group to follow
        # the condition a group used as a subgroup cannot be deactivated.
        params = {"delete": orjson.dumps([support_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{test_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(test_group, [])

        # Test adding or removing subgroups from a deactivated group.
        do_deactivate_user_group(support_group, acting_user=None)

        params = {"delete": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [])

        params = {"add": orjson.dumps([leadership_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{support_group.id}/subgroups", info=params)
        self.assert_json_success(result)
        self.assert_subgroup_membership(support_group, [leadership_group])

        # Test that a deactivated group cannot be used as a subgroup.
        params = {"add": orjson.dumps([support_group.id]).decode()}
        result = self.client_post(f"/json/user_groups/{test_group.id}/subgroups", info=params)
        self.assert_json_error(result, "User group is deactivated.")

    def test_permission_to_add_subgroups_to_group(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        leadership_group = check_add_user_group(realm, "leadership", [othello], acting_user=othello)
        support_group = check_add_user_group(realm, "support", [hamlet], acting_user=hamlet)

        def check_adding_subgroups_to_group(acting_user: str, error_msg: str | None = None) -> None:
            params = {"add": orjson.dumps([leadership_group.id]).decode()}
            self.assert_subgroup_membership(support_group, [])

            result = self.api_post(
                self.example_user(acting_user),
                f"/api/v1/user_groups/{support_group.id}/subgroups",
                info=params,
            )
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_subgroup_membership(support_group, [leadership_group])
                # Remove the subgroup to test further cases.
                remove_subgroups_from_user_group(
                    support_group, [leadership_group], acting_user=None
                )
            else:
                self.assert_json_error(result, error_msg)

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        # Set manage permissions to "Nobody" group to test permission
        # with can_add_members_group.
        do_change_user_group_permission_setting(
            support_group,
            "can_manage_group",
            nobody_group,
            acting_user=None,
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            nobody_group,
            acting_user=None,
        )

        do_change_user_group_permission_setting(
            support_group,
            "can_add_members_group",
            nobody_group,
            acting_user=None,
        )
        check_adding_subgroups_to_group("desdemona", "Insufficient permission")

        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm=realm, is_system_group=True
        )
        do_change_user_group_permission_setting(
            support_group,
            "can_add_members_group",
            owners_group,
            acting_user=None,
        )
        check_adding_subgroups_to_group("iago", "Insufficient permission")
        check_adding_subgroups_to_group("desdemona")

        # Test case when setting is set to a non-system group.
        prospero = self.example_user("prospero")
        test_group = check_add_user_group(realm, "test", [prospero], acting_user=prospero)
        do_change_user_group_permission_setting(
            support_group,
            "can_add_members_group",
            test_group,
            acting_user=None,
        )
        check_adding_subgroups_to_group("desdemona", "Insufficient permission")
        check_adding_subgroups_to_group("prospero")

        # Test case when setting is set to an anonymous group.
        setting_group = self.create_or_update_anonymous_group_for_setting(
            direct_members=[othello],
            direct_subgroups=[owners_group],
        )
        do_change_user_group_permission_setting(
            support_group,
            "can_add_members_group",
            setting_group,
            acting_user=None,
        )
        check_adding_subgroups_to_group("prospero", "Insufficient permission")
        check_adding_subgroups_to_group("iago", "Insufficient permission")
        check_adding_subgroups_to_group("desdemona")
        check_adding_subgroups_to_group("othello")

        # Set can_add_members_group setting to nobody, so we can test
        # managing permissions as well.
        do_change_user_group_permission_setting(
            support_group,
            "can_add_members_group",
            nobody_group,
            acting_user=None,
        )

        # Check permission as per can_manage_group setting.
        setting_group = self.create_or_update_anonymous_group_for_setting(
            direct_members=[othello],
            direct_subgroups=[owners_group],
        )
        do_change_user_group_permission_setting(
            support_group,
            "can_manage_group",
            setting_group,
            acting_user=None,
        )
        check_adding_subgroups_to_group("iago", "Insufficient permission")
        check_adding_subgroups_to_group("desdemona")
        check_adding_subgroups_to_group("othello")

        # Check permission as per can_manage_all_groups setting.
        do_change_user_group_permission_setting(
            support_group,
            "can_manage_group",
            nobody_group,
            acting_user=None,
        )
        setting_group = self.create_or_update_anonymous_group_for_setting(
            direct_members=[othello],
            direct_subgroups=[owners_group],
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            setting_group,
            acting_user=None,
        )
        check_adding_subgroups_to_group("iago", "Insufficient permission")
        check_adding_subgroups_to_group("desdemona")
        check_adding_subgroups_to_group("othello")

    def test_permission_to_remove_subgroups_from_group(self) -> None:
        realm = get_realm("zulip")
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        leadership_group = check_add_user_group(realm, "leadership", [othello], acting_user=othello)
        support_group = check_add_user_group(realm, "support", [hamlet], acting_user=hamlet)
        add_subgroups_to_user_group(support_group, [leadership_group], acting_user=None)

        def check_remove_subgroups_from_group(
            acting_user: str, error_msg: str | None = None
        ) -> None:
            params = {"delete": orjson.dumps([leadership_group.id]).decode()}
            self.assert_subgroup_membership(support_group, [leadership_group])

            result = self.api_post(
                self.example_user(acting_user),
                f"/api/v1/user_groups/{support_group.id}/subgroups",
                info=params,
            )
            if error_msg is None:
                self.assert_json_success(result)
                self.assert_subgroup_membership(support_group, [])
                # Add the subgroup again to test further cases.
                add_subgroups_to_user_group(support_group, [leadership_group], acting_user=None)
            else:
                self.assert_json_error(result, error_msg)

        # Set permissions for managing all groups to "Nobody" group to
        # test permission with can_manage_group.
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_manage_all_groups", nobody_group, acting_user=None
        )

        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm=realm, is_system_group=True
        )
        do_change_user_group_permission_setting(
            support_group,
            "can_manage_group",
            owners_group,
            acting_user=None,
        )
        check_remove_subgroups_from_group("iago", "Insufficient permission")
        check_remove_subgroups_from_group("desdemona")

        # Test case when setting is set to a non-system group.
        prospero = self.example_user("prospero")
        test_group = check_add_user_group(realm, "test", [prospero], acting_user=prospero)
        do_change_user_group_permission_setting(
            support_group,
            "can_manage_group",
            test_group,
            acting_user=None,
        )
        check_remove_subgroups_from_group("desdemona", "Insufficient permission")
        check_remove_subgroups_from_group("prospero")

        # Test case when setting is set to an anonymous group.
        setting_group = self.create_or_update_anonymous_group_for_setting(
            direct_members=[othello],
            direct_subgroups=[owners_group],
        )
        do_change_user_group_permission_setting(
            support_group,
            "can_manage_group",
            setting_group,
            acting_user=None,
        )
        check_remove_subgroups_from_group("prospero", "Insufficient permission")
        check_remove_subgroups_from_group("iago", "Insufficient permission")
        check_remove_subgroups_from_group("desdemona")
        check_remove_subgroups_from_group("othello")

        # Set can_manage_group setting to nobody, so we can test
        # can_manage_all_groups behavior.
        do_change_user_group_permission_setting(
            support_group,
            "can_manage_group",
            nobody_group,
            acting_user=None,
        )

        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            owners_group,
            acting_user=None,
        )
        check_remove_subgroups_from_group("desdemona")
        check_remove_subgroups_from_group("iago", "Insufficient permission")

        # Test case when setting is set to a non-system group.
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            test_group,
            acting_user=None,
        )
        check_remove_subgroups_from_group("desdemona", "Insufficient permission")
        check_remove_subgroups_from_group("prospero")

        # Test case when setting is set to an anonymous group.
        setting_group = self.create_or_update_anonymous_group_for_setting(
            direct_members=[othello],
            direct_subgroups=[owners_group],
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_manage_all_groups",
            setting_group,
            acting_user=None,
        )
        check_remove_subgroups_from_group("prospero", "Insufficient permission")
        check_remove_subgroups_from_group("iago", "Insufficient permission")
        check_remove_subgroups_from_group("desdemona")
        check_remove_subgroups_from_group("othello")

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
        result = self.client_get(f"/json/user_groups/123456/members/{iago.id}")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_cordelia = self.lear_user("cordelia")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [lear_cordelia], acting_user=lear_cordelia
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

        # Check membership of deactivated user.
        do_deactivate_user(iago, acting_user=None)
        result = self.client_get(f"/json/user_groups/{admins_group.id}/members/{iago.id}")
        self.assert_json_error(result, "User is deactivated")

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
        result = self.client_get("/json/user_groups/123456/members")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_cordelia = self.lear_user("cordelia")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [lear_cordelia], acting_user=lear_cordelia
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

        # Check deactivated users are not returned in members list.
        do_deactivate_user(shiva, acting_user=None)
        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/members", info=params).content
        )
        self.assertCountEqual(result_dict["members"], [])

        params = {"direct_member_only": orjson.dumps(False).decode()}
        result_dict = orjson.loads(
            self.client_get(f"/json/user_groups/{moderators_group.id}/members", info=params).content
        )
        self.assertCountEqual(result_dict["members"], [desdemona.id, iago.id])

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
        result = self.client_get("/json/user_groups/123456/subgroups")
        self.assert_json_error(result, "Invalid user group")

        lear_realm = get_realm("lear")
        lear_cordelia = self.lear_user("cordelia")
        lear_test_group = check_add_user_group(
            lear_realm, "test", [lear_cordelia], acting_user=lear_cordelia
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
        iago = self.example_user("iago")
        other_realm = do_create_realm("other", "Other Realm")
        other_user_group = check_add_user_group(other_realm, "user_group", [], acting_user=iago)
        realm = get_realm("zulip")
        zulip_group = check_add_user_group(realm, "zulip_test", [], acting_user=iago)

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
