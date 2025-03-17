"use strict";

const assert = require("node:assert/strict");

const example_settings = require("./lib/example_settings.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const group_permission_settings = zrequire("group_permission_settings");
const user_groups = zrequire("user_groups");
const {set_realm} = zrequire("state_data");

const realm = {};
set_realm(realm);

const get_test_subgroup = (id) => ({
    name: `Subgroup id: ${id} `,
    id,
    members: new Set([4]),
    is_system_group: false,
    direct_subgroup_ids: new Set([]),
    can_join_group: 1,
    can_leave_group: 1,
    can_manage_group: 1,
    can_mention_group: 1,
    deactivated: false,
});

run_test("user_groups", () => {
    const students = {
        description: "Students group",
        name: "Students",
        creator_id: null,
        date_created: 1596710000,
        id: 0,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
        can_add_members_group: 1,
        can_join_group: 1,
        can_leave_group: 1,
        can_manage_group: 1,
        can_mention_group: 2,
        can_remove_members_group: 1,
        deactivated: false,
    };

    const params = {};
    params.realm_user_groups = [
        students,
        get_test_subgroup(4),
        get_test_subgroup(5),
        get_test_subgroup(6),
    ];
    const user_id_not_in_any_group = 0;
    const user_id_part_of_a_group = 2;
    const user_id_associated_via_subgroup = 4;

    user_groups.initialize(params);
    assert.deepEqual(user_groups.get_user_group_from_id(students.id), students);

    const admins = {
        name: "Admins",
        description: "foo",
        creator_id: null,
        date_created: 1596710000,
        id: 1,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
        can_add_members_group: 1,
        can_join_group: 1,
        can_leave_group: 1,
        can_manage_group: 1,
        can_mention_group: 2,
        can_remove_members_group: 1,
        deactivated: false,
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([1, 2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5, 6]),
        can_join_group: 1,
        can_leave_group: 1,
        can_manage_group: 1,
        can_mention_group: 1,
        deactivated: false,
    };
    const deactivated_group = {
        name: "Deactivated test group",
        id: 3,
        members: new Set([1, 2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5, 6]),
        can_join_group: 1,
        can_leave_group: 1,
        can_manage_group: 1,
        can_mention_group: 1,
        deactivated: true,
    };

    user_groups.add(admins);
    assert.deepEqual(user_groups.get_user_group_from_id(admins.id), admins);

    assert.equal(user_groups.maybe_get_user_group_from_id(99), undefined);
    assert.deepEqual(user_groups.get_user_group_from_id(admins.id), admins);

    const update_name_event = {
        group_id: admins.id,
        data: {
            name: "new admins",
        },
    };
    const admins_group = user_groups.get_user_group_from_id(admins.id);
    user_groups.update(update_name_event, admins_group);
    assert.equal(user_groups.get_user_group_from_id(admins.id).name, "new admins");

    const update_des_event = {
        group_id: admins.id,
        data: {
            description: "administer",
        },
    };
    user_groups.update(update_des_event, admins_group);
    assert.equal(user_groups.get_user_group_from_id(admins.id).description, "administer");

    assert.throws(() => user_groups.get_user_group_from_id(all.id), {
        name: "Error",
        message: "Unknown group_id in get_user_group_from_id: 2",
    });
    user_groups.remove(students);

    assert.throws(() => user_groups.get_user_group_from_id(students.id), {
        name: "Error",
        message: "Unknown group_id in get_user_group_from_id: 0",
    });

    assert.equal(user_groups.get_user_group_from_name(all.name), undefined);
    assert.equal(user_groups.get_user_group_from_name("new admins").id, 1);

    user_groups.add(all);
    user_groups.add(deactivated_group);
    const user_groups_array = user_groups.get_realm_user_groups();
    assert.equal(user_groups_array.length, 5);
    assert.equal(user_groups_array[1].name, "Everyone");
    assert.equal(user_groups_array[0].name, "new admins");

    const all_user_groups_array = user_groups.get_realm_user_groups(true);
    assert.equal(all_user_groups_array.length, 6);
    assert.equal(all_user_groups_array[2].name, "Deactivated test group");
    assert.equal(all_user_groups_array[1].name, "Everyone");
    assert.equal(all_user_groups_array[0].name, "new admins");

    const groups_of_users = user_groups.get_user_groups_of_user(user_id_part_of_a_group);
    assert.equal(groups_of_users.length, 1);
    assert.equal(groups_of_users[0].name, "Everyone");

    const groups_of_users_via_subgroup = user_groups.get_user_groups_of_user(
        user_id_associated_via_subgroup,
    );
    assert.deepEqual(groups_of_users_via_subgroup.map((group) => group.id).sort(), [2, 4, 5, 6]);
    assert.equal(groups_of_users_via_subgroup.length, 4);

    const groups_of_users_nomatch = user_groups.get_user_groups_of_user(user_id_not_in_any_group);
    assert.equal(groups_of_users_nomatch.length, 0);

    assert.ok(!user_groups.is_direct_member_of(4, admins.id));
    assert.ok(user_groups.is_direct_member_of(3, admins.id));

    user_groups.add_members(all.id, [5, 4]);
    assert.deepEqual(user_groups.get_user_group_from_id(all.id).members, new Set([1, 2, 3, 5, 4]));

    user_groups.remove_members(all.id, [1, 4]);
    assert.deepEqual(user_groups.get_user_group_from_id(all.id).members, new Set([2, 3, 5]));

    user_groups.add_subgroups(all.id, [2, 3]);
    assert.deepEqual(
        user_groups.get_user_group_from_id(all.id).direct_subgroup_ids,
        new Set([2, 3, 5, 4, 6]),
    );

    user_groups.remove_subgroups(all.id, [2, 4]);
    assert.deepEqual(
        user_groups.get_user_group_from_id(all.id).direct_subgroup_ids,
        new Set([3, 5, 6]),
    );

    assert.ok(user_groups.is_user_group(admins));
    const object = {
        name: "core",
        id: 3,
    };
    assert.ok(!user_groups.is_user_group(object));

    const update_deactivated_event = {
        group_id: admins.id,
        data: {
            deactivated: true,
        },
    };
    user_groups.update(update_deactivated_event, admins_group);
    assert.ok(user_groups.get_user_group_from_id(admins.id).deactivated);

    user_groups.init();
    assert.equal(user_groups.get_realm_user_groups().length, 0);

    blueslip.expect("error", "Could not find user group", 5);
    assert.equal(user_groups.is_direct_member_of(15, -1), false);
    user_groups.add_members(-9999);
    user_groups.remove_members(-9999);
    user_groups.add_subgroups(-9999);
    user_groups.remove_subgroups(-9999);
});

run_test("get_recursive_subgroups", () => {
    const admins = {
        name: "Admins",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    };
    const test = {
        name: "Test",
        id: 3,
        members: new Set([3, 4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    };
    const foo = {
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.add(admins);
    user_groups.add(all);
    user_groups.add(test);
    user_groups.add(foo);

    // This test setup has a state that won't appear in real data: Groups 2 and 3
    // each contain the other. We test this corner case because it is a simple way
    // to verify whether our algorithm correctly avoids visiting groups multiple times
    // when determining recursive subgroups.
    // A test case that can occur in practice and would be problematic without this
    // optimization is a tree where each layer connects to every node in the next layer.
    assert.deepEqual(user_groups.get_recursive_subgroups(admins), new Set([4]));
    assert.deepEqual(user_groups.get_recursive_subgroups(all), new Set([4, 1, 2, 3]));
    assert.deepEqual(user_groups.get_recursive_subgroups(test), new Set([2, 4, 1, 3]));
    assert.deepEqual(user_groups.get_recursive_subgroups(foo), new Set([]));

    user_groups.add_subgroups(foo.id, [9999]);
    const foo_group = user_groups.get_user_group_from_id(foo.id);
    blueslip.expect("error", "Could not find subgroup", 2);
    assert.deepEqual(user_groups.get_recursive_subgroups(foo_group), undefined);
    assert.deepEqual(user_groups.get_recursive_subgroups(test), undefined);
});

run_test("get_recursive_group_members", () => {
    const admins = {
        name: "Admins",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    };
    const test = {
        name: "Test",
        id: 3,
        members: new Set([3, 4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    };
    const foo = {
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.add(admins);
    user_groups.add(all);
    user_groups.add(test);
    user_groups.add(foo);

    // This test setup has a state that won't appear in real data: Groups 2 and 3
    // each contain the other. We test this corner case because it is a simple way
    // to verify whether our algorithm correctly avoids visiting groups multiple times
    // when determining recursive subgroups.
    // A test case that can occur in practice and would be problematic without this
    // optimization is a tree where each layer connects to every node in the next layer.
    assert.deepEqual([...user_groups.get_recursive_group_members(admins)].sort(), [1, 6, 7]);
    assert.deepEqual(
        [...user_groups.get_recursive_group_members(all)].sort(),
        [1, 2, 3, 4, 5, 6, 7],
    );
    assert.deepEqual(
        [...user_groups.get_recursive_group_members(test)].sort(),
        [1, 2, 3, 4, 5, 6, 7],
    );
    assert.deepEqual([...user_groups.get_recursive_group_members(foo)].sort(), [6, 7]);

    user_groups.add_subgroups(foo.id, [9999]);
    const foo_group = user_groups.get_user_group_from_id(foo.id);
    blueslip.expect("error", "Could not find subgroup", 2);
    assert.deepEqual([...user_groups.get_recursive_group_members(foo_group)].sort(), [6, 7]);
    assert.deepEqual([...user_groups.get_recursive_group_members(test)].sort(), [3, 4, 5]);
});

run_test("get_associated_subgroups", () => {
    const admins = {
        name: "Admins",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    };
    const test = {
        name: "Test",
        id: 3,
        members: new Set([1, 4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    };
    const foo = {
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    const admins_group = user_groups.add(admins);
    const all_group = user_groups.add(all);
    user_groups.add(test);
    user_groups.add(foo);

    // This test setup has a state that won't appear in real data: Groups 2 and 3
    // each contain the other. We test this corner case because it is a simple way
    // to verify whether our algorithm correctly avoids visiting groups multiple times
    // when determining recursive subgroups.
    // A test case that can occur in practice and would be problematic without this
    // optimization is a tree where each layer connects to every node in the next layer.
    let associated_subgroups = user_groups.get_associated_subgroups(admins_group, 6);
    assert.deepEqual(associated_subgroups.length, 1);
    assert.equal(associated_subgroups[0].id, 4);

    associated_subgroups = user_groups.get_associated_subgroups(all_group, 1);
    assert.deepEqual(associated_subgroups.length, 2);
    assert.deepEqual(associated_subgroups.map((group) => group.id).sort(), [1, 3]);

    associated_subgroups = user_groups.get_associated_subgroups(admins, 2);
    assert.deepEqual(associated_subgroups.length, 0);
});

run_test("is_user_in_group", () => {
    const admins = {
        name: "Admins",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    };
    const test = {
        name: "Test",
        id: 3,
        members: new Set([4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    };
    const foo = {
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };
    user_groups.add(admins);
    user_groups.add(all);
    user_groups.add(test);
    user_groups.add(foo);

    assert.equal(user_groups.is_user_in_group(admins.id, 1), true);
    assert.equal(user_groups.is_user_in_group(admins.id, 6), true);
    assert.equal(user_groups.is_user_in_group(admins.id, 3), false);

    assert.equal(user_groups.is_user_in_group(all.id, 2), true);
    assert.equal(user_groups.is_user_in_group(all.id, 1), true);
    assert.equal(user_groups.is_user_in_group(all.id, 6), true);

    assert.equal(user_groups.is_user_in_group(test.id, 4), true);
    assert.equal(user_groups.is_user_in_group(test.id, 1), true);
    assert.equal(user_groups.is_user_in_group(test.id, 6), true);
    assert.equal(user_groups.is_user_in_group(test.id, 3), false);

    assert.equal(user_groups.is_user_in_group(foo.id, 6), true);
    assert.equal(user_groups.is_user_in_group(foo.id, 3), false);

    // Check when passing direct_member_only as true.
    assert.equal(user_groups.is_user_in_group(admins.id, 1, true), true);
    assert.equal(user_groups.is_user_in_group(admins.id, 6, true), false);

    assert.equal(user_groups.is_user_in_group(all.id, 2, true), true);
    assert.equal(user_groups.is_user_in_group(all.id, 1, true), false);
    assert.equal(user_groups.is_user_in_group(all.id, 6, true), false);

    assert.equal(user_groups.is_user_in_group(test.id, 4, true), true);
    assert.equal(user_groups.is_user_in_group(test.id, 1, true), false);
    assert.equal(user_groups.is_user_in_group(test.id, 6, true), false);

    assert.equal(user_groups.is_user_in_setting_group(test.id, 4), true);
    assert.equal(user_groups.is_user_in_setting_group(test.id, 1), true);
    assert.equal(user_groups.is_user_in_setting_group(test.id, 6), true);
    assert.equal(user_groups.is_user_in_setting_group(test.id, 3), false);

    const anonymous_setting_group = {
        direct_members: [8, 9],
        direct_subgroups: [admins.id, test.id],
    };
    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 8), true);
    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 9), true);
    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 10), false);

    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 1), true);
    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 4), true);
    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 6), true);
    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 2), false);
    assert.equal(user_groups.is_user_in_setting_group(anonymous_setting_group, 3), false);

    blueslip.expect("error", "Could not find user group");
    assert.equal(user_groups.is_user_in_group(1111, 3), false);

    user_groups.add_subgroups(foo.id, [9999]);
    blueslip.expect("error", "Could not find subgroup");
    assert.equal(user_groups.is_user_in_group(admins.id, 6), false);
});

run_test("get_realm_user_groups_for_dropdown_list_widget", ({override}) => {
    const nobody = {
        name: "role:nobody",
        description: "foo",
        id: 1,
        members: new Set([]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };
    const owners = {
        name: "role:owners",
        description: "foo",
        id: 2,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };
    const admins = {
        name: "role:administrators",
        description: "foo",
        id: 3,
        members: new Set([2]),
        is_system_group: true,
        direct_subgroup_ids: new Set([1]),
    };
    const moderators = {
        name: "role:moderators",
        description: "foo",
        id: 4,
        members: new Set([3]),
        is_system_group: true,
        direct_subgroup_ids: new Set([2]),
    };
    const members = {
        name: "role:members",
        description: "foo",
        id: 5,
        members: new Set([4]),
        is_system_group: true,
        direct_subgroup_ids: new Set([6]),
    };
    const everyone = {
        name: "role:everyone",
        description: "foo",
        id: 6,
        members: new Set([]),
        is_system_group: true,
        direct_subgroup_ids: new Set([4]),
    };
    const full_members = {
        name: "role:fullmembers",
        description: "foo",
        id: 7,
        members: new Set([5]),
        is_system_group: true,
        direct_subgroup_ids: new Set([3]),
    };
    const internet = {
        name: "role:internet",
        id: 8,
        members: new Set([]),
        is_system_group: true,
        direct_subgroup_ids: new Set([5]),
    };
    const students = {
        description: "Students group",
        name: "Students",
        id: 9,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
    };

    override(
        realm,
        "server_supported_permission_settings",
        example_settings.server_supported_permission_settings,
    );

    let expected_groups_list = [
        {name: "translated: Admins, moderators, members and guests", unique_id: 6},
        {name: "translated: Admins, moderators and members", unique_id: 5},
        {name: "translated: Admins, moderators and full members", unique_id: 7},
        {name: "translated: Admins and moderators", unique_id: 4},
        {name: "translated: Admins", unique_id: 3},
        {name: "translated: Owners", unique_id: 2},
    ];

    user_groups.initialize({
        realm_user_groups: [
            nobody,
            owners,
            admins,
            moderators,
            members,
            everyone,
            full_members,
            internet,
            students,
        ],
    });

    assert.deepEqual(
        group_permission_settings.get_realm_user_groups_for_dropdown_list_widget(
            "can_remove_subscribers_group",
            "stream",
        ),
        expected_groups_list,
    );

    expected_groups_list = [
        {name: "translated: Admins, moderators, members and guests", unique_id: 6},
        {name: "translated: Admins, moderators and members", unique_id: 5},
    ];

    assert.deepEqual(
        group_permission_settings.get_realm_user_groups_for_dropdown_list_widget(
            "can_access_all_users_group",
            "realm",
        ),
        expected_groups_list,
    );

    assert.throws(
        () =>
            group_permission_settings.get_realm_user_groups_for_dropdown_list_widget(
                "invalid_setting",
                "stream",
            ),
        {
            name: "Error",
            message: "Invalid setting: invalid_setting",
        },
    );
});

run_test("get_display_group_name", () => {
    const admins = {
        name: "role:administrators",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    };
    const all = {
        name: "role:everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    };
    const students = {
        name: "Students",
        id: 3,
        members: new Set([1, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.initialize({
        realm_user_groups: [admins, all, students],
    });

    assert.equal(user_groups.get_display_group_name(admins.name), "translated: Administrators");
    assert.equal(
        user_groups.get_display_group_name(all.name),
        "translated: Everyone including guests",
    );
    assert.equal(user_groups.get_display_group_name(students.name), "Students");
});

run_test("get_potential_subgroups", () => {
    // Remove existing groups.
    user_groups.init();

    const admins = {
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    };
    const students = {
        name: "Students",
        id: 3,
        members: new Set([4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };
    const teachers = {
        name: "Teachers",
        id: 4,
        members: new Set([6, 7, 8]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };
    const science = {
        name: "Science",
        id: 5,
        members: new Set([9]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.initialize({
        realm_user_groups: [admins, all, students, teachers, science],
    });

    function get_potential_subgroup_ids(group_id) {
        return user_groups
            .get_potential_subgroups(group_id)
            .map((subgroup) => subgroup.id)
            .sort();
    }

    assert.deepEqual(get_potential_subgroup_ids(all.id), [teachers.id, science.id]);
    assert.deepEqual(get_potential_subgroup_ids(admins.id), [students.id, science.id]);
    assert.deepEqual(get_potential_subgroup_ids(teachers.id), [students.id, science.id]);
    assert.deepEqual(get_potential_subgroup_ids(students.id), [admins.id, teachers.id, science.id]);
    assert.deepEqual(get_potential_subgroup_ids(science.id), [
        admins.id,
        all.id,
        students.id,
        teachers.id,
    ]);

    user_groups.add_subgroups(all.id, [teachers.id]);
    user_groups.add_subgroups(teachers.id, [science.id]);
    assert.deepEqual(get_potential_subgroup_ids(all.id), [science.id]);
    assert.deepEqual(get_potential_subgroup_ids(admins.id), [students.id, science.id]);
    assert.deepEqual(get_potential_subgroup_ids(teachers.id), [students.id]);
    assert.deepEqual(get_potential_subgroup_ids(students.id), [admins.id, teachers.id, science.id]);
    assert.deepEqual(get_potential_subgroup_ids(science.id), [students.id]);
});

run_test("is_subgroup_of_target_group", () => {
    const admins = {
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };
    const moderators = {
        name: "Moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    };
    const all = {
        name: "Everyone",
        id: 3,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2, 4]),
    };
    const students = {
        name: "Students",
        id: 4,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.initialize({
        realm_user_groups: [admins, moderators, all, students],
    });

    assert.ok(user_groups.is_subgroup_of_target_group(moderators.id, admins.id));
    assert.ok(!user_groups.is_subgroup_of_target_group(admins.id, moderators.id));

    assert.ok(user_groups.is_subgroup_of_target_group(all.id, admins.id));
    assert.ok(user_groups.is_subgroup_of_target_group(all.id, moderators.id));
    assert.ok(user_groups.is_subgroup_of_target_group(all.id, students.id));

    assert.ok(!user_groups.is_subgroup_of_target_group(students.id, all.id));
});

run_test("group_has_permission", () => {
    const admins = {
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };
    const moderators = {
        name: "Moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    };
    const all = {
        name: "Everyone",
        id: 3,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2, 4]),
    };
    const students = {
        name: "Students",
        id: 4,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.initialize({
        realm_user_groups: [admins, moderators, all, students],
    });

    let setting_value = admins.id;
    let group_id = admins.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = moderators.id;
    assert.ok(!user_groups.group_has_permission(setting_value, group_id));

    setting_value = all.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = admins.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    setting_value = {
        direct_members: [2],
        direct_subgroups: [admins.id],
    };
    group_id = admins.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = moderators.id;
    assert.ok(!user_groups.group_has_permission(setting_value, group_id));

    setting_value = {
        direct_members: [2],
        direct_subgroups: [moderators.id, students.id],
    };
    group_id = admins.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = moderators.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = students.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = all.id;
    assert.ok(!user_groups.group_has_permission(setting_value, group_id));

    setting_value = {
        direct_members: [2],
        direct_subgroups: [moderators.id, all.id],
    };

    group_id = admins.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = moderators.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = students.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));

    group_id = all.id;
    assert.ok(user_groups.group_has_permission(setting_value, group_id));
});

run_test("get_assigned_group_permission_object", ({override}) => {
    const admins = {
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };
    const moderators = {
        name: "Moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    };
    const all = {
        name: "Everyone",
        id: 3,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2, 4]),
    };
    const students = {
        name: "Students",
        id: 4,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
    };

    user_groups.initialize({
        realm_user_groups: [admins, moderators, all, students],
    });
    override(
        realm,
        "server_supported_permission_settings",
        example_settings.server_supported_permission_settings,
    );

    const setting_name = "can_manage_group";
    let setting_value = moderators.id;
    let group_id = all.id;
    let can_edit_settings = false;
    assert.equal(
        group_permission_settings.get_assigned_permission_object(
            setting_value,
            setting_name,
            group_id,
            can_edit_settings,
            "group",
        ),
        undefined,
    );

    group_id = students.id;
    assert.equal(
        group_permission_settings.get_assigned_permission_object(
            setting_value,
            setting_name,
            group_id,
            can_edit_settings,
            "group",
        ),
        undefined,
    );

    group_id = moderators.id;
    let permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message: "translated: You are not allowed to remove this permission.",
    });

    group_id = admins.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message: "translated: You are not allowed to remove this permission.",
    });

    setting_value = {
        direct_members: [2],
        direct_subgroups: [moderators.id, students.id],
    };
    group_id = all.id;
    assert.equal(
        group_permission_settings.get_assigned_permission_object(
            setting_value,
            setting_name,
            group_id,
            can_edit_settings,
            "group",
        ),
        undefined,
    );

    group_id = students.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message: "translated: You are not allowed to remove this permission.",
    });

    group_id = moderators.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message: "translated: You are not allowed to remove this permission.",
    });

    group_id = admins.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message: "translated: You are not allowed to remove this permission.",
    });

    can_edit_settings = true;

    setting_value = moderators.id;
    group_id = all.id;
    assert.equal(
        group_permission_settings.get_assigned_permission_object(
            setting_value,
            setting_name,
            group_id,
            can_edit_settings,
            "group",
        ),
        undefined,
    );

    group_id = students.id;
    assert.equal(
        group_permission_settings.get_assigned_permission_object(
            setting_value,
            setting_name,
            group_id,
            can_edit_settings,
            "group",
        ),
        undefined,
    );

    group_id = moderators.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: true,
    });

    group_id = admins.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message:
            "translated: This group has this permission because it's a subgroup of Moderators.",
    });

    setting_value = {
        direct_members: [2],
        direct_subgroups: [moderators.id, students.id],
    };
    group_id = all.id;
    assert.equal(
        group_permission_settings.get_assigned_permission_object(
            setting_value,
            setting_name,
            group_id,
            can_edit_settings,
            "group",
        ),
        undefined,
    );

    group_id = students.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: true,
    });

    group_id = moderators.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: true,
    });

    group_id = admins.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message:
            "translated: This group has this permission because it's a subgroup of Moderators.",
    });

    setting_value = {
        direct_members: [2],
        direct_subgroups: [all.id],
    };
    group_id = admins.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message:
            "translated: This group has this permission because it's a subgroup of Everyone.",
    });

    group_id = moderators.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message:
            "translated: This group has this permission because it's a subgroup of Everyone.",
    });

    group_id = students.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: false,
        tooltip_message:
            "translated: This group has this permission because it's a subgroup of Everyone.",
    });

    group_id = all.id;
    permission_obj = group_permission_settings.get_assigned_permission_object(
        setting_value,
        setting_name,
        group_id,
        can_edit_settings,
        "group",
    );
    assert.deepEqual(permission_obj, {
        setting_name,
        can_edit: true,
    });
});
