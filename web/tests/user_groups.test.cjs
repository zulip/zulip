"use strict";

const assert = require("node:assert/strict");

const {make_user_group} = require("./lib/example_group.cjs");
const {make_realm} = require("./lib/example_realm.cjs");
const example_settings = require("./lib/example_settings.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const group_permission_settings = zrequire("group_permission_settings");
const user_groups = zrequire("user_groups");
const {initialize_user_settings} = zrequire("user_settings");
const {set_current_user, set_realm} = zrequire("state_data");

const realm = make_realm();
set_realm(realm);

const get_test_subgroup = (id) =>
    make_user_group({
        name: `Subgroup id: ${id} `,
        id,
        members: new Set([4]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        can_join_group: 1,
        can_leave_group: 1,
        can_manage_group: 1,
        can_mention_group: 1,
        deactivated: false,
    });

run_test("user_groups", () => {
    const students = make_user_group({
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
    });

    const params = {
        realm_user_groups: [
            students,
            get_test_subgroup(4),
            get_test_subgroup(5),
            get_test_subgroup(6),
        ],
    };
    const user_id_not_in_any_group = 0;
    const user_id_part_of_a_group = 2;
    const user_id_associated_via_subgroup = 4;

    user_groups.initialize(params);
    assert.deepEqual(user_groups.get_user_group_from_id(students.id), students);

    const admins = make_user_group({
        name: "Admins",
        description: "foo",
        creator_id: null,
        date_created: 1596710000,
        id: 1,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        can_add_members_group: 1,
        can_join_group: 1,
        can_leave_group: 1,
        can_manage_group: 1,
        can_mention_group: 2,
        can_remove_members_group: 1,
        deactivated: false,
    });
    const all = make_user_group({
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
    });
    const deactivated_group = make_user_group({
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
    });

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
    assert.deepEqual(
        groups_of_users_via_subgroup.map((group) => group.id).toSorted(),
        [2, 4, 5, 6],
    );
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
    const admins = make_user_group({
        name: "Admins",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    });
    const test = make_user_group({
        name: "Test",
        id: 3,
        members: new Set([3, 4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    });
    const foo = make_user_group({
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

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
    assert.deepEqual(user_groups.get_recursive_subgroups(foo), new Set());

    user_groups.add_subgroups(foo.id, [9999]);
    const foo_group = user_groups.get_user_group_from_id(foo.id);
    blueslip.expect("error", "Could not find subgroup", 2);
    assert.deepEqual(user_groups.get_recursive_subgroups(foo_group), undefined);
    assert.deepEqual(user_groups.get_recursive_subgroups(test), undefined);
});

run_test("get_recursive_group_members", () => {
    const admins = make_user_group({
        name: "Admins",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    });
    const test = make_user_group({
        name: "Test",
        id: 3,
        members: new Set([3, 4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    });
    const foo = make_user_group({
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

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
    assert.deepEqual([...user_groups.get_recursive_group_members(admins)].toSorted(), [1, 6, 7]);
    assert.deepEqual(
        [...user_groups.get_recursive_group_members(all)].toSorted(),
        [1, 2, 3, 4, 5, 6, 7],
    );
    assert.deepEqual(
        [...user_groups.get_recursive_group_members(test)].toSorted(),
        [1, 2, 3, 4, 5, 6, 7],
    );
    assert.deepEqual([...user_groups.get_recursive_group_members(foo)].toSorted(), [6, 7]);

    user_groups.add_subgroups(foo.id, [9999]);
    const foo_group = user_groups.get_user_group_from_id(foo.id);
    blueslip.expect("error", "Could not find subgroup", 2);
    assert.deepEqual([...user_groups.get_recursive_group_members(foo_group)].toSorted(), [6, 7]);
    assert.deepEqual([...user_groups.get_recursive_group_members(test)].toSorted(), [3, 4, 5]);
});

run_test("get_associated_subgroups", () => {
    const admins = make_user_group({
        name: "Admins",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    });
    const test = make_user_group({
        name: "Test",
        id: 3,
        members: new Set([1, 4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    });
    const foo = make_user_group({
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

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
    assert.deepEqual(associated_subgroups.map((group) => group.id).toSorted(), [1, 3]);

    associated_subgroups = user_groups.get_associated_subgroups(admins, 2);
    assert.deepEqual(associated_subgroups.length, 0);
});

run_test("is_user_in_group", () => {
    const admins = make_user_group({
        name: "Admins",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    });
    const test = make_user_group({
        name: "Test",
        id: 3,
        members: new Set([4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    });
    const foo = make_user_group({
        name: "Foo",
        id: 4,
        members: new Set([6, 7]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
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
    const nobody = make_user_group({
        name: "role:nobody",
        description: "foo",
        id: 1,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });
    const owners = make_user_group({
        name: "role:owners",
        description: "foo",
        id: 2,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });
    const admins = make_user_group({
        name: "role:administrators",
        description: "foo",
        id: 3,
        members: new Set([2]),
        is_system_group: true,
        direct_subgroup_ids: new Set([1]),
    });
    const moderators = make_user_group({
        name: "role:moderators",
        description: "foo",
        id: 4,
        members: new Set([3]),
        is_system_group: true,
        direct_subgroup_ids: new Set([2]),
    });
    const members = make_user_group({
        name: "role:members",
        description: "foo",
        id: 5,
        members: new Set([4]),
        is_system_group: true,
        direct_subgroup_ids: new Set([6]),
    });
    const everyone = make_user_group({
        name: "role:everyone",
        description: "foo",
        id: 6,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set([4]),
    });
    const full_members = make_user_group({
        name: "role:fullmembers",
        description: "foo",
        id: 7,
        members: new Set([5]),
        is_system_group: true,
        direct_subgroup_ids: new Set([3]),
    });
    const internet = make_user_group({
        name: "role:internet",
        id: 8,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set([5]),
    });
    const students = make_user_group({
        description: "Students group",
        name: "Students",
        id: 9,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
    });

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
        {name: "Students", unique_id: 9},
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
    const admins = make_user_group({
        name: "role:administrators",
        description: "foo",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    });
    const all = make_user_group({
        name: "role:everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    });
    const students = make_user_group({
        name: "Students",
        id: 3,
        members: new Set([1, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

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

    const admins = make_user_group({
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 2,
        members: new Set([2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 3]),
    });
    const students = make_user_group({
        name: "Students",
        id: 3,
        members: new Set([4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const teachers = make_user_group({
        name: "Teachers",
        id: 4,
        members: new Set([6, 7, 8]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const science = make_user_group({
        name: "Science",
        id: 5,
        members: new Set([9]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

    user_groups.initialize({
        realm_user_groups: [admins, all, students, teachers, science],
    });

    function get_potential_subgroup_ids(group_id) {
        return user_groups
            .get_potential_subgroups(group_id)
            .map((subgroup) => subgroup.id)
            .toSorted();
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
    const admins = make_user_group({
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const moderators = make_user_group({
        name: "Moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 3,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2, 4]),
    });
    const students = make_user_group({
        name: "Students",
        id: 4,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

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
    const admins = make_user_group({
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const moderators = make_user_group({
        name: "Moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 3,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2, 4]),
    });
    const students = make_user_group({
        name: "Students",
        id: 4,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

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
    const admins = make_user_group({
        name: "Administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const moderators = make_user_group({
        name: "Moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    });
    const all = make_user_group({
        name: "Everyone",
        id: 3,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2, 4]),
    });
    const students = make_user_group({
        name: "Students",
        id: 4,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

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

run_test("realm_has_deactivated_user_groups", () => {
    user_groups.init();
    const active_group = make_user_group({
        name: "Active group",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });

    user_groups.initialize({
        realm_user_groups: [active_group],
    });

    assert.equal(user_groups.realm_has_deactivated_user_groups(), false);

    const deactivated_group = make_user_group({
        name: "Deactivated group",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    user_groups.add(deactivated_group);

    assert.equal(user_groups.realm_has_deactivated_user_groups(), true);
});

run_test("get_all_realm_user_groups", () => {
    user_groups.init();
    const nobody = make_user_group({
        name: "role:nobody",
        id: 1,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    const internet = make_user_group({
        name: "role:internet",
        id: 2,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    const custom = make_user_group({
        name: "Custom group",
        id: 3,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    const deactivated = make_user_group({
        name: "Deactivated",
        id: 4,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });

    user_groups.initialize({
        realm_user_groups: [nobody, internet, custom, deactivated],
    });

    // By default, excludes deactivated and internet groups.
    // Includes system groups (unlike get_realm_user_groups).
    let groups = user_groups.get_all_realm_user_groups();
    const group_names = new Set(groups.map((g) => g.name));
    assert.ok(group_names.has("role:nobody"));
    assert.ok(group_names.has("Custom group"));
    assert.ok(!group_names.has("role:internet"));
    assert.ok(!group_names.has("Deactivated"));

    // Include deactivated groups.
    groups = user_groups.get_all_realm_user_groups(true);
    assert.ok(groups.some((g) => g.name === "Deactivated"));

    // Include internet group.
    groups = user_groups.get_all_realm_user_groups(false, true);
    assert.ok(groups.some((g) => g.name === "role:internet"));
    assert.ok(!groups.some((g) => g.name === "Deactivated"));

    // Include both deactivated and internet.
    groups = user_groups.get_all_realm_user_groups(true, true);
    assert.equal(groups.length, 4);
});

run_test("get_user_groups_allowed_to_mention", ({override}) => {
    user_groups.init();
    const current_user = {user_id: 1};
    set_current_user(current_user);

    const mentionable = make_user_group({
        name: "Mentionable",
        id: 1,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        // User 1 is in group 1, which is set as can_mention_group.
        can_mention_group: 1,
        deactivated: false,
    });
    const not_mentionable = make_user_group({
        name: "Not mentionable",
        id: 2,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        // User 1 is not in group 2.
        can_mention_group: 2,
        deactivated: false,
    });

    user_groups.initialize({
        realm_user_groups: [mentionable, not_mentionable],
    });

    override(current_user, "user_id", 1);

    const allowed = user_groups.get_user_groups_allowed_to_mention();
    assert.equal(allowed.length, 1);
    assert.equal(allowed[0].name, "Mentionable");
});

run_test("is_empty_group", () => {
    user_groups.init();
    const empty_group = make_user_group({
        name: "Empty",
        id: 1,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const non_empty_group = make_user_group({
        name: "Non-empty",
        id: 2,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const group_with_empty_subgroups = make_user_group({
        name: "Parent of empties",
        id: 3,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
    });
    const group_with_non_empty_subgroup = make_user_group({
        name: "Parent of non-empty",
        id: 4,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    });

    user_groups.initialize({
        realm_user_groups: [
            empty_group,
            non_empty_group,
            group_with_empty_subgroups,
            group_with_non_empty_subgroup,
        ],
    });

    assert.equal(user_groups.is_empty_group(empty_group.id), true);
    assert.equal(user_groups.is_empty_group(non_empty_group.id), false);
    assert.equal(user_groups.is_empty_group(group_with_empty_subgroups.id), true);
    assert.equal(user_groups.is_empty_group(group_with_non_empty_subgroup.id), false);

    // Test with nested empty subgroups.
    const deeply_nested_empty = make_user_group({
        name: "Deep empty",
        id: 5,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([3]),
    });
    user_groups.add(deeply_nested_empty);
    assert.equal(user_groups.is_empty_group(deeply_nested_empty.id), true);

    // Error case: nonexistent group.
    blueslip.expect("error", "Could not find user group");
    assert.equal(user_groups.is_empty_group(9999), false);

    // Error case: subgroup not found.
    const group_with_missing_subgroup = make_user_group({
        name: "Bad parent",
        id: 6,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([8888]),
    });
    user_groups.add(group_with_missing_subgroup);
    blueslip.expect("error", "Could not find subgroup");
    assert.equal(user_groups.is_empty_group(group_with_missing_subgroup.id), false);
});

run_test("is_setting_group_empty", () => {
    user_groups.init();
    const empty_group = make_user_group({
        name: "Empty",
        id: 1,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const non_empty_group = make_user_group({
        name: "Non-empty",
        id: 2,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

    user_groups.initialize({
        realm_user_groups: [empty_group, non_empty_group],
    });

    // Numeric form (group ID).
    assert.equal(user_groups.is_setting_group_empty(empty_group.id), true);
    assert.equal(user_groups.is_setting_group_empty(non_empty_group.id), false);

    // GroupSettingValue form with direct members.
    assert.equal(
        user_groups.is_setting_group_empty({
            direct_members: [1],
            direct_subgroups: [],
        }),
        false,
    );

    // GroupSettingValue form with empty members and empty subgroups.
    assert.equal(
        user_groups.is_setting_group_empty({
            direct_members: [],
            direct_subgroups: [empty_group.id],
        }),
        true,
    );

    // GroupSettingValue form with non-empty subgroup.
    assert.equal(
        user_groups.is_setting_group_empty({
            direct_members: [],
            direct_subgroups: [non_empty_group.id],
        }),
        false,
    );

    // Completely empty GroupSettingValue.
    assert.equal(
        user_groups.is_setting_group_empty({
            direct_members: [],
            direct_subgroups: [],
        }),
        true,
    );
});

run_test("is_setting_group_set_to_nobody_group", () => {
    user_groups.init();
    const nobody = make_user_group({
        name: "role:nobody",
        id: 1,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });
    const admins = make_user_group({
        name: "role:administrators",
        id: 2,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });

    user_groups.initialize({
        realm_user_groups: [nobody, admins],
    });

    // Numeric form: nobody group.
    assert.equal(user_groups.is_setting_group_set_to_nobody_group(nobody.id), true);
    // Numeric form: non-nobody group.
    assert.equal(user_groups.is_setting_group_set_to_nobody_group(admins.id), false);

    // GroupSettingValue form: empty (equivalent to nobody).
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group({
            direct_members: [],
            direct_subgroups: [],
        }),
        true,
    );

    // GroupSettingValue form: has members.
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group({
            direct_members: [1],
            direct_subgroups: [],
        }),
        false,
    );

    // GroupSettingValue form: has subgroups.
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group({
            direct_members: [],
            direct_subgroups: [2],
        }),
        false,
    );
});

run_test("get_supergroups_of_user_group", () => {
    user_groups.init();
    const child = make_user_group({
        name: "Child",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    const parent1 = make_user_group({
        name: "Parent 1",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
        deactivated: false,
    });
    const parent2 = make_user_group({
        name: "Parent 2",
        id: 3,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
        deactivated: false,
    });
    const unrelated = make_user_group({
        name: "Unrelated",
        id: 4,
        members: new Set([4]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });

    user_groups.initialize({
        realm_user_groups: [child, parent1, parent2, unrelated],
    });

    const supergroups = user_groups.get_supergroups_of_user_group(child.id);
    assert.equal(supergroups.length, 2);
    assert.deepEqual(supergroups.map((g) => g.id).toSorted(), [2, 3]);

    // Group with no parents.
    const no_parents = user_groups.get_supergroups_of_user_group(unrelated.id);
    assert.equal(no_parents.length, 0);
});

run_test("check_group_can_be_subgroup", () => {
    user_groups.init();
    const target = make_user_group({
        name: "Target",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([3]),
        deactivated: false,
    });
    const candidate = make_user_group({
        name: "Candidate",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    const existing_subgroup = make_user_group({
        name: "Existing subgroup",
        id: 3,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    const deactivated_group = make_user_group({
        name: "Deactivated",
        id: 4,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    // Group that contains target as a recursive subgroup (would create cycle).
    const would_cycle = make_user_group({
        name: "Would cycle",
        id: 5,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]),
        deactivated: false,
    });

    user_groups.initialize({
        realm_user_groups: [target, candidate, existing_subgroup, deactivated_group, would_cycle],
    });

    // Valid candidate.
    assert.equal(user_groups.check_group_can_be_subgroup(candidate, target), true);
    // Deactivated group cannot be a subgroup.
    assert.equal(user_groups.check_group_can_be_subgroup(deactivated_group, target), false);
    // Self-reference not allowed.
    assert.equal(user_groups.check_group_can_be_subgroup(target, target), false);
    // Already a direct subgroup.
    assert.equal(user_groups.check_group_can_be_subgroup(existing_subgroup, target), false);
    // Would create a cycle: would_cycle contains target.
    assert.equal(user_groups.check_group_can_be_subgroup(would_cycle, target), false);
});

run_test("is_group_larger_than", () => {
    user_groups.init();
    const small_group = make_user_group({
        name: "Small",
        id: 1,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const subgroup = make_user_group({
        name: "Subgroup",
        id: 2,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const parent_group = make_user_group({
        name: "Parent",
        id: 3,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]),
    });

    user_groups.initialize({
        realm_user_groups: [small_group, subgroup, parent_group],
    });

    const small = user_groups.get_user_group_from_id(small_group.id);
    const parent = user_groups.get_user_group_from_id(parent_group.id);

    // Group with 2 members, max_size=5: not larger.
    assert.equal(user_groups.is_group_larger_than(small, 5), false);
    // Group with 2 members, max_size=1: larger.
    assert.equal(user_groups.is_group_larger_than(small, 1), true);
    // Exact boundary: 2 members, max_size=2: not larger (uses >).
    assert.equal(user_groups.is_group_larger_than(small, 2), false);

    // Parent with 2 direct + 2 from subgroup = 4 unique members.
    assert.equal(user_groups.is_group_larger_than(parent, 3), true);
    assert.equal(user_groups.is_group_larger_than(parent, 5), false);

    // Test with overlapping members in subgroup.
    const overlap_subgroup = make_user_group({
        name: "Overlap sub",
        id: 4,
        members: new Set([1, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const overlap_parent = make_user_group({
        name: "Overlap parent",
        id: 5,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4]),
    });
    user_groups.add(overlap_subgroup);
    user_groups.add(overlap_parent);

    const overlap = user_groups.get_user_group_from_id(overlap_parent.id);
    // Unique members: {1, 2, 5} = 3.
    assert.equal(user_groups.is_group_larger_than(overlap, 2), true);
    assert.equal(user_groups.is_group_larger_than(overlap, 3), false);
});

run_test("get_direct_subgroups_of_group", () => {
    user_groups.init();
    const sub1 = make_user_group({
        name: "Sub 1",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const sub2 = make_user_group({
        name: "Sub 2",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const parent = make_user_group({
        name: "Parent",
        id: 3,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 2]),
    });

    user_groups.initialize({
        realm_user_groups: [sub1, sub2, parent],
    });

    const parent_group = user_groups.get_user_group_from_id(parent.id);
    const direct_subgroups = user_groups.get_direct_subgroups_of_group(parent_group);
    assert.equal(direct_subgroups.length, 2);
    assert.deepEqual(direct_subgroups.map((g) => g.id).toSorted(), [1, 2]);

    // Group with no subgroups.
    const sub1_group = user_groups.get_user_group_from_id(sub1.id);
    const no_subgroups = user_groups.get_direct_subgroups_of_group(sub1_group);
    assert.equal(no_subgroups.length, 0);
});

run_test("convert_name_to_display_name_for_groups", () => {
    user_groups.init();
    const system_group = make_user_group({
        name: "role:administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });
    const custom_group = make_user_group({
        name: "Engineering",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

    user_groups.initialize({
        realm_user_groups: [system_group, custom_group],
    });

    const groups = [
        user_groups.get_user_group_from_id(system_group.id),
        user_groups.get_user_group_from_id(custom_group.id),
    ];
    const converted = user_groups.convert_name_to_display_name_for_groups(groups);

    // System group should get translated display name.
    assert.equal(converted[0].name, "translated: Administrators");
    // Custom group keeps its original name.
    assert.equal(converted[1].name, "Engineering");
});

run_test("format_group_list", () => {
    user_groups.init();
    initialize_user_settings({user_settings: {}});
    const group1 = make_user_group({
        name: "Admins",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    const group2 = make_user_group({
        name: "Moderators",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });

    user_groups.initialize({
        realm_user_groups: [group1, group2],
    });

    const groups = [
        user_groups.get_user_group_from_id(group1.id),
        user_groups.get_user_group_from_id(group2.id),
    ];
    const result = user_groups.format_group_list(groups);
    // Intl.ListFormat with "conjunction" joins with "and".
    assert.ok(result.includes("Admins"));
    assert.ok(result.includes("Moderators"));
});

run_test("check_system_user_group_allowed_for_setting", ({override}) => {
    const setting_config = {
        require_system_group: false,
        allow_internet_group: false,
        allow_nobody_group: true,
        allow_everyone_group: false,
        default_group_name: "role:members",
        default_for_system_groups: null,
        allowed_system_groups: [],
    };

    // Internet group blocked when allow_internet_group is false.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:internet",
            setting_config,
            false,
        ),
        false,
    );

    // Internet group allowed when allow_internet_group is true.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:internet",
            {...setting_config, allow_internet_group: true},
            false,
        ),
        true,
    );

    // Nobody group allowed when allow_nobody_group is true and not for_new_settings_ui.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:nobody",
            setting_config,
            false,
        ),
        true,
    );

    // Nobody group blocked when for_new_settings_ui is true.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:nobody",
            setting_config,
            true,
        ),
        false,
    );

    // Nobody group blocked when allow_nobody_group is false.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:nobody",
            {...setting_config, allow_nobody_group: false},
            false,
        ),
        false,
    );

    // Everyone group blocked when allow_everyone_group is false.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:everyone",
            setting_config,
            false,
        ),
        false,
    );

    // Everyone group allowed when allow_everyone_group is true.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:everyone",
            {...setting_config, allow_everyone_group: true},
            false,
        ),
        true,
    );

    // allowed_system_groups whitelist: group not in list is blocked.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:administrators",
            {...setting_config, allowed_system_groups: ["role:owners", "role:moderators"]},
            false,
        ),
        false,
    );

    // allowed_system_groups whitelist: group in list is allowed.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:administrators",
            {...setting_config, allowed_system_groups: ["role:administrators", "role:moderators"]},
            false,
        ),
        true,
    );

    // Fullmembers hidden in new settings UI when waiting period is 0.
    override(realm, "realm_waiting_period_threshold", 0);
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            setting_config,
            true,
        ),
        false,
    );

    // Fullmembers shown when waiting period > 0.
    override(realm, "realm_waiting_period_threshold", 3);
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            setting_config,
            true,
        ),
        true,
    );

    // Fullmembers shown when not in new settings UI, even with 0 waiting period.
    override(realm, "realm_waiting_period_threshold", 0);
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            setting_config,
            false,
        ),
        true,
    );

    // Regular system group passes all checks.
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:members",
            setting_config,
            false,
        ),
        true,
    );
});
