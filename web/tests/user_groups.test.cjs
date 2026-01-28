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
const {set_realm, set_current_user} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

const realm = make_realm();
set_realm(realm);

const current_user = {};
set_current_user(current_user);

// Initialize user_settings for tests that need it
const user_settings = {
    default_language: "en",
};
initialize_user_settings({user_settings});

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

// ===== NEW COMPREHENSIVE TEST COVERAGE =====
// The following tests are added to achieve full coverage of user_groups.ts
// All new code is commented to explain the purpose and coverage goals

run_test("check_system_user_group_allowed_for_setting", ({override}) => {
    // Test the complex conditional logic in check_system_user_group_allowed_for_setting
    // This function has multiple branches based on group names, settings, and realm configuration
    
    // REQUIREMENT 1: Test allowed_system_groups logic
    // Test configuration with specific allowed system groups
    const restricted_config = {
        allow_internet_group: true,
        allow_nobody_group: true,
        allow_everyone_group: true,
        allowed_system_groups: ["role:administrators"], // Only administrators allowed
    };
    
    // Group in the allowed list should pass
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:administrators",
            restricted_config,
            false,
        ),
        true,
        "role:administrators should be allowed when in allowed_system_groups list",
    );
    
    // System group NOT in the allowed list should fail
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:members",
            restricted_config,
            false,
        ),
        false,
        "role:members should be blocked when not in allowed_system_groups list",
    );
    
    // REQUIREMENT 2: Test realm_waiting_period_threshold logic for role:fullmembers
    const base_config = {
        allow_internet_group: true,
        allow_nobody_group: true,
        allow_everyone_group: true,
        allowed_system_groups: [],
    };
    
    // Scenario 1: for_new_settings_ui is true and threshold is 0 (should be false)
    override(realm, "realm_waiting_period_threshold", 0);
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            base_config,
            true,
        ),
        false,
        "role:fullmembers should be hidden in new settings UI when realm_waiting_period_threshold is 0",
    );
    
    // Scenario 2: for_new_settings_ui is true and threshold > 0 (should be true)
    override(realm, "realm_waiting_period_threshold", 7);
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            base_config,
            true,
        ),
        true,
        "role:fullmembers should be allowed in new settings UI when realm_waiting_period_threshold > 0",
    );
    
    // Scenario 3: for_new_settings_ui is false (should be true regardless of threshold)
    override(realm, "realm_waiting_period_threshold", 0);
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            base_config,
            false,
        ),
        true,
        "role:fullmembers should be allowed in old settings UI regardless of realm_waiting_period_threshold",
    );
    
    // REQUIREMENT 3: Test all scenarios for for_new_settings_ui on role:nobody
    const nobody_allowed_config = {
        allow_internet_group: true,
        allow_nobody_group: true, // Explicitly allow nobody group
        allow_everyone_group: true,
        allowed_system_groups: [],
    };
    
    // When for_new_settings_ui is false, role:nobody should be allowed if allow_nobody_group is true
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:nobody",
            nobody_allowed_config,
            false,
        ),
        true,
        "role:nobody should be allowed when allow_nobody_group is true and for_new_settings_ui is false",
    );
    
    // When for_new_settings_ui is true, role:nobody should return false even if allow_nobody_group is true
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:nobody",
            nobody_allowed_config,
            true,
        ),
        false,
        "role:nobody should be blocked when for_new_settings_ui is true, even if allow_nobody_group is true",
    );
    
    // Additional basic tests for other system groups
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:internet",
            {allow_internet_group: false, allow_nobody_group: true, allow_everyone_group: true, allowed_system_groups: []},
            false,
        ),
        false,
        "role:internet should be blocked when allow_internet_group is false",
    );
    
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:everyone",
            {allow_internet_group: true, allow_nobody_group: true, allow_everyone_group: false, allowed_system_groups: []},
            false,
        ),
        false,
        "role:everyone should be blocked when allow_everyone_group is false",
    );
    
    // Test non-system groups always pass through
    const unrestricted_config = {
        allow_internet_group: false,
        allow_nobody_group: false,
        allow_everyone_group: false,
        allowed_system_groups: [], // Empty list means no restrictions
    };
    
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting(
            "custom_group",
            unrestricted_config,
            true,
        ),
        true,
        "Non-system groups should always be allowed when allowed_system_groups is empty",
    );
});

run_test("is_empty_group", () => {
    // Test is_empty_group function with various group configurations
    // This function checks both direct members and recursive subgroups
    
    user_groups.init();
    
    // Create test groups with different member and subgroup configurations
    const empty_group = make_user_group({
        name: "Empty",
        id: 1,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const group_with_members = make_user_group({
        name: "WithMembers",
        id: 2,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const empty_parent_with_empty_subgroups = make_user_group({
        name: "EmptyParentEmptySubgroups",
        id: 3,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]), // Points to empty_group
    });
    
    const empty_parent_with_member_subgroups = make_user_group({
        name: "EmptyParentMemberSubgroups",
        id: 4,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]), // Points to group_with_members
    });
    
    const nested_empty_group = make_user_group({
        name: "NestedEmpty",
        id: 5,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([3]), // Points to empty_parent_with_empty_subgroups
    });
    
    user_groups.initialize({
        realm_user_groups: [
            empty_group,
            group_with_members,
            empty_parent_with_empty_subgroups,
            empty_parent_with_member_subgroups,
            nested_empty_group,
        ],
    });
    
    // Test basic empty group
    assert.equal(
        user_groups.is_empty_group(empty_group.id),
        true,
        "Group with no members and no subgroups should be empty",
    );
    
    // Test group with direct members
    assert.equal(
        user_groups.is_empty_group(group_with_members.id),
        false,
        "Group with direct members should not be empty",
    );
    
    // Test empty parent with empty subgroups (recursive check)
    assert.equal(
        user_groups.is_empty_group(empty_parent_with_empty_subgroups.id),
        true,
        "Group with no members and only empty subgroups should be empty",
    );
    
    // Test empty parent with non-empty subgroups
    assert.equal(
        user_groups.is_empty_group(empty_parent_with_member_subgroups.id),
        false,
        "Group with no direct members but non-empty subgroups should not be empty",
    );
    
    // Test deeply nested empty groups
    assert.equal(
        user_groups.is_empty_group(nested_empty_group.id),
        true,
        "Deeply nested group should be empty if all recursive subgroups are empty",
    );
    
    // Test error handling for non-existent group
    blueslip.expect("error", "Could not find user group");
    assert.equal(
        user_groups.is_empty_group(9999),
        false,
        "Non-existent group should return false and log error",
    );
    
    // Test error handling for non-existent subgroup
    const group_with_invalid_subgroup = make_user_group({
        name: "InvalidSubgroup",
        id: 6,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([9999]), // Non-existent subgroup
    });
    
    user_groups.add(group_with_invalid_subgroup);
    blueslip.expect("error", "Could not find subgroup");
    assert.equal(
        user_groups.is_empty_group(group_with_invalid_subgroup.id),
        false,
        "Group with invalid subgroup should return false and log error",
    );
});

run_test("is_setting_group_empty", () => {
    // Test is_setting_group_empty function with both number and object setting values
    // This function handles two different input types: group IDs and anonymous setting groups
    
    user_groups.init();
    
    const empty_group = make_user_group({
        name: "Empty",
        id: 1,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const non_empty_group = make_user_group({
        name: "NonEmpty",
        id: 2,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    user_groups.initialize({
        realm_user_groups: [empty_group, non_empty_group],
    });
    
    // Test with group ID (number) - empty group
    assert.equal(
        user_groups.is_setting_group_empty(empty_group.id),
        true,
        "Empty group ID should return true",
    );
    
    // Test with group ID (number) - non-empty group
    assert.equal(
        user_groups.is_setting_group_empty(non_empty_group.id),
        false,
        "Non-empty group ID should return false",
    );
    
    // Test with anonymous setting group - empty
    const empty_anonymous_group = {
        direct_members: [],
        direct_subgroups: [empty_group.id],
    };
    assert.equal(
        user_groups.is_setting_group_empty(empty_anonymous_group),
        true,
        "Anonymous group with no direct members and only empty subgroups should be empty",
    );
    
    // Test with anonymous setting group - has direct members
    const anonymous_group_with_members = {
        direct_members: [1, 2],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_setting_group_empty(anonymous_group_with_members),
        false,
        "Anonymous group with direct members should not be empty",
    );
    
    // Test with anonymous setting group - has non-empty subgroups
    const anonymous_group_with_non_empty_subgroups = {
        direct_members: [],
        direct_subgroups: [non_empty_group.id],
    };
    assert.equal(
        user_groups.is_setting_group_empty(anonymous_group_with_non_empty_subgroups),
        false,
        "Anonymous group with non-empty subgroups should not be empty",
    );
    
    // Test with anonymous setting group - completely empty
    const completely_empty_anonymous_group = {
        direct_members: [],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_setting_group_empty(completely_empty_anonymous_group),
        true,
        "Anonymous group with no members and no subgroups should be empty",
    );
});

run_test("is_setting_group_set_to_nobody_group", () => {
    // Test is_setting_group_set_to_nobody_group function
    // This function checks if a setting group is effectively set to "nobody"
    
    user_groups.init();
    
    const nobody_group = make_user_group({
        name: "role:nobody",
        id: 1,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });
    
    const regular_group = make_user_group({
        name: "regular_group",
        id: 2,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    user_groups.initialize({
        realm_user_groups: [nobody_group, regular_group],
    });
    
    // Test with nobody group ID
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(nobody_group.id),
        true,
        "Group with name 'role:nobody' should return true",
    );
    
    // Test with regular group ID
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(regular_group.id),
        false,
        "Regular group should return false",
    );
    
    // Test with anonymous setting group - empty (equivalent to nobody)
    const empty_anonymous_group = {
        direct_members: [],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(empty_anonymous_group),
        true,
        "Anonymous group with no members and no subgroups should be equivalent to nobody",
    );
    
    // Test with anonymous setting group - has members
    const anonymous_group_with_members = {
        direct_members: [1],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(anonymous_group_with_members),
        false,
        "Anonymous group with members should not be equivalent to nobody",
    );
    
    // Test with anonymous setting group - has subgroups
    const anonymous_group_with_subgroups = {
        direct_members: [],
        direct_subgroups: [regular_group.id],
    };
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(anonymous_group_with_subgroups),
        false,
        "Anonymous group with subgroups should not be equivalent to nobody",
    );
});

run_test("realm_has_deactivated_user_groups", () => {
    // Test realm_has_deactivated_user_groups function
    // This function checks if there are any deactivated non-system groups in the realm
    
    user_groups.init();
    
    // Test with no groups
    assert.equal(
        user_groups.realm_has_deactivated_user_groups(),
        false,
        "Realm with no groups should not have deactivated groups",
    );
    
    // Test with only active groups
    const active_group = make_user_group({
        name: "Active",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    
    user_groups.initialize({
        realm_user_groups: [active_group],
    });
    
    assert.equal(
        user_groups.realm_has_deactivated_user_groups(),
        false,
        "Realm with only active groups should not have deactivated groups",
    );
    
    // Test with deactivated groups
    const deactivated_group = make_user_group({
        name: "Deactivated",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    
    user_groups.add(deactivated_group);
    
    assert.equal(
        user_groups.realm_has_deactivated_user_groups(),
        true,
        "Realm with deactivated groups should return true",
    );
    
    // Test with deactivated system groups (should be ignored)
    user_groups.init();
    const deactivated_system_group = make_user_group({
        name: "role:deactivated_system",
        id: 3,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    
    user_groups.initialize({
        realm_user_groups: [deactivated_system_group],
    });
    
    assert.equal(
        user_groups.realm_has_deactivated_user_groups(),
        false,
        "Realm with only deactivated system groups should return false",
    );
});

run_test("get_all_realm_user_groups", () => {
    // Test get_all_realm_user_groups function with various filter options
    // This function includes system groups and has options for deactivated and internet groups
    
    user_groups.init();
    
    const regular_group = make_user_group({
        name: "Regular",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    
    const deactivated_group = make_user_group({
        name: "Deactivated",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    
    const system_group = make_user_group({
        name: "role:administrators",
        id: 3,
        members: new Set([3]),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    
    const internet_group = make_user_group({
        name: "role:internet",
        id: 4,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    
    user_groups.initialize({
        realm_user_groups: [regular_group, deactivated_group, system_group, internet_group],
    });
    
    // Test default behavior (exclude deactivated, exclude internet)
    let result = user_groups.get_all_realm_user_groups();
    assert.equal(result.length, 2, "Default should return regular and system groups");
    assert.deepEqual(
        result.map((g) => g.id).toSorted(),
        [regular_group.id, system_group.id],
        "Should include regular and system groups, exclude deactivated and internet",
    );
    
    // Test include deactivated
    result = user_groups.get_all_realm_user_groups(true);
    assert.equal(result.length, 3, "Should include deactivated groups");
    assert.deepEqual(
        result.map((g) => g.id).toSorted(),
        [regular_group.id, deactivated_group.id, system_group.id],
        "Should include deactivated groups but still exclude internet",
    );
    
    // Test include internet group
    result = user_groups.get_all_realm_user_groups(false, true);
    assert.equal(result.length, 3, "Should include internet group");
    assert.deepEqual(
        result.map((g) => g.id).toSorted(),
        [regular_group.id, system_group.id, internet_group.id],
        "Should include internet group but exclude deactivated",
    );
    
    // Test include both deactivated and internet
    result = user_groups.get_all_realm_user_groups(true, true);
    assert.equal(result.length, 4, "Should include all groups");
    assert.deepEqual(
        result.map((g) => g.id).toSorted(),
        [regular_group.id, deactivated_group.id, system_group.id, internet_group.id],
        "Should include all groups when both flags are true",
    );
    
    // Verify groups are sorted by ID
    const unsorted_groups = [
        make_user_group({name: "Z", id: 10, is_system_group: false}),
        make_user_group({name: "A", id: 5, is_system_group: false}),
        make_user_group({name: "M", id: 7, is_system_group: false}),
    ];
    
    user_groups.init();
    user_groups.initialize({realm_user_groups: unsorted_groups});
    
    result = user_groups.get_all_realm_user_groups();
    assert.deepEqual(
        result.map((g) => g.id),
        [5, 7, 10],
        "Groups should be sorted by ID",
    );
});

run_test("is_user_in_any_group", () => {
    // Test is_user_in_any_group function
    // This function checks if a user is in any of the provided group IDs
    
    user_groups.init();
    
    const group1 = make_user_group({
        name: "Group1",
        id: 1,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const group2 = make_user_group({
        name: "Group2",
        id: 2,
        members: new Set([3, 4]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const group3 = make_user_group({
        name: "Group3",
        id: 3,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]), // Contains group1 as subgroup
    });
    
    user_groups.initialize({
        realm_user_groups: [group1, group2, group3],
    });
    
    // Test user in one of the groups
    assert.equal(
        user_groups.is_user_in_any_group([group1.id, group2.id], 1),
        true,
        "User 1 should be found in group1",
    );
    
    // Test user not in any of the groups
    assert.equal(
        user_groups.is_user_in_any_group([group1.id, group2.id], 5),
        false,
        "User 5 should not be found in group1 or group2",
    );
    
    // Test user in subgroup (recursive membership)
    assert.equal(
        user_groups.is_user_in_any_group([group3.id], 1),
        true,
        "User 1 should be found in group3 via subgroup membership",
    );
    
    // Test direct member only flag
    assert.equal(
        user_groups.is_user_in_any_group([group3.id], 1, true),
        false,
        "User 1 should not be found in group3 when checking direct members only",
    );
    
    assert.equal(
        user_groups.is_user_in_any_group([group3.id], 5, true),
        true,
        "User 5 should be found in group3 as direct member",
    );
    
    // Test empty group list
    assert.equal(
        user_groups.is_user_in_any_group([], 1),
        false,
        "Empty group list should return false",
    );
});

run_test("is_group_larger_than", () => {
    // Test is_group_larger_than function
    // This function efficiently checks if a group's total membership exceeds a threshold
    
    user_groups.init();
    
    const small_group = make_user_group({
        name: "Small",
        id: 1,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const medium_group = make_user_group({
        name: "Medium",
        id: 2,
        members: new Set([3, 4, 5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const parent_group = make_user_group({
        name: "Parent",
        id: 3,
        members: new Set([6]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 2]), // Contains small_group and medium_group
    });
    
    const large_direct_group = make_user_group({
        name: "LargeDirect",
        id: 4,
        members: new Set([7, 8, 9, 10, 11, 12]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    user_groups.initialize({
        realm_user_groups: [small_group, medium_group, parent_group, large_direct_group],
    });
    
    // Test small group
    assert.equal(
        user_groups.is_group_larger_than(small_group, 5),
        false,
        "Small group (2 members) should not be larger than 5",
    );
    
    assert.equal(
        user_groups.is_group_larger_than(small_group, 1),
        true,
        "Small group (2 members) should be larger than 1",
    );
    
    // Test group with direct members exceeding threshold
    assert.equal(
        user_groups.is_group_larger_than(large_direct_group, 5),
        true,
        "Group with 6 direct members should be larger than 5",
    );
    
    assert.equal(
        user_groups.is_group_larger_than(large_direct_group, 3),
        true,
        "Group with 6 direct members should be larger than 3",
    );
    
    // Test parent group with subgroups (total: 1 + 2 + 3 = 6 members)
    assert.equal(
        user_groups.is_group_larger_than(parent_group, 5),
        true,
        "Parent group with subgroups (6 total members) should be larger than 5",
    );
    
    assert.equal(
        user_groups.is_group_larger_than(parent_group, 6),
        false,
        "Parent group with subgroups (6 total members) should not be larger than 6",
    );
    
    assert.equal(
        user_groups.is_group_larger_than(parent_group, 10),
        false,
        "Parent group with subgroups (6 total members) should not be larger than 10",
    );
    
    // Test edge case: exactly at threshold
    assert.equal(
        user_groups.is_group_larger_than(small_group, 2),
        false,
        "Group with exactly 2 members should not be larger than 2",
    );
    
    // Test with undefined subgroups (error case)
    const group_with_invalid_subgroup = make_user_group({
        name: "InvalidSubgroup",
        id: 5,
        members: new Set([13]),
        is_system_group: false,
        direct_subgroup_ids: new Set([9999]), // Non-existent subgroup
    });
    
    user_groups.add(group_with_invalid_subgroup);
    blueslip.expect("error", "Could not find subgroup");
    assert.equal(
        user_groups.is_group_larger_than(group_with_invalid_subgroup, 5),
        false,
        "Group with invalid subgroup should return false",
    );
});

run_test("check_group_can_be_subgroup", () => {
    // Test check_group_can_be_subgroup function
    // This function validates if a group can be added as a subgroup to another group
    
    user_groups.init();
    
    const active_group = make_user_group({
        name: "Active",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    
    const deactivated_group = make_user_group({
        name: "Deactivated",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    
    const parent_group = make_user_group({
        name: "Parent",
        id: 3,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]), // Already contains active_group
        deactivated: false,
    });
    
    const child_group = make_user_group({
        name: "Child",
        id: 4,
        members: new Set([4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([3]), // Contains parent_group (would create cycle)
        deactivated: false,
    });
    
    user_groups.initialize({
        realm_user_groups: [active_group, deactivated_group, parent_group, child_group],
    });
    
    // Test adding active group to new parent (should work)
    assert.equal(
        user_groups.check_group_can_be_subgroup(active_group, child_group),
        true,
        "Active group should be able to be added as subgroup",
    );
    
    // Test adding deactivated group (should fail)
    assert.equal(
        user_groups.check_group_can_be_subgroup(deactivated_group, active_group),
        false,
        "Deactivated group should not be able to be added as subgroup",
    );
    
    // Test adding group to itself (should fail)
    assert.equal(
        user_groups.check_group_can_be_subgroup(active_group, active_group),
        false,
        "Group should not be able to be added as subgroup to itself",
    );
    
    // Test adding group that's already a subgroup (should fail)
    assert.equal(
        user_groups.check_group_can_be_subgroup(active_group, parent_group),
        false,
        "Group that's already a subgroup should not be addable again",
    );
    
    // Test adding group that would create a cycle (should fail)
    assert.equal(
        user_groups.check_group_can_be_subgroup(parent_group, child_group),
        false,
        "Adding group that would create cycle should fail",
    );
    
    // Test valid addition
    const independent_group = make_user_group({
        name: "Independent",
        id: 5,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    
    user_groups.add(independent_group);
    
    assert.equal(
        user_groups.check_group_can_be_subgroup(independent_group, active_group),
        true,
        "Independent group should be able to be added as subgroup",
    );
});

run_test("get_direct_subgroups_of_group", () => {
    // Test get_direct_subgroups_of_group function
    // This function returns the direct subgroups of a given group
    
    user_groups.init();
    
    const subgroup1 = make_user_group({
        name: "Subgroup1",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const subgroup2 = make_user_group({
        name: "Subgroup2",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const parent_group = make_user_group({
        name: "Parent",
        id: 3,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1, 2]),
    });
    
    const empty_parent = make_user_group({
        name: "EmptyParent",
        id: 4,
        members: new Set([4]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    user_groups.initialize({
        realm_user_groups: [subgroup1, subgroup2, parent_group, empty_parent],
    });
    
    // Test group with subgroups
    const direct_subgroups = user_groups.get_direct_subgroups_of_group(parent_group);
    assert.equal(direct_subgroups.length, 2, "Should return 2 direct subgroups");
    assert.deepEqual(
        direct_subgroups.map((g) => g.id).toSorted(),
        [1, 2],
        "Should return the correct subgroups",
    );
    
    // Test group with no subgroups
    const empty_subgroups = user_groups.get_direct_subgroups_of_group(empty_parent);
    assert.equal(empty_subgroups.length, 0, "Should return empty array for group with no subgroups");
});

run_test("convert_name_to_display_name_for_groups", () => {
    // Test convert_name_to_display_name_for_groups function
    // This function converts system group names to display names
    
    const system_group = make_user_group({
        name: "role:administrators",
        id: 1,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });
    
    const regular_group = make_user_group({
        name: "Custom Group",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const input_groups = [system_group, regular_group];
    const result = user_groups.convert_name_to_display_name_for_groups(input_groups);
    
    assert.equal(result.length, 2, "Should return same number of groups");
    assert.equal(
        result[0].name,
        "translated: Administrators",
        "System group name should be converted to display name",
    );
    assert.equal(
        result[1].name,
        "Custom Group",
        "Regular group name should remain unchanged",
    );
    
    // Verify other properties are preserved
    assert.equal(result[0].id, system_group.id, "Group ID should be preserved");
    assert.deepEqual(result[0].members, system_group.members, "Group members should be preserved");
});

run_test("format_group_list", () => {
    // Test format_group_list function
    // This function formats a list of groups into a readable string
    
    const group1 = make_user_group({name: "Administrators", id: 1});
    const group2 = make_user_group({name: "Moderators", id: 2});
    const group3 = make_user_group({name: "Members", id: 3});
    
    // Test single group
    assert.equal(
        user_groups.format_group_list([group1]),
        "Administrators",
        "Single group should return just the name",
    );
    
    // Test two groups
    assert.equal(
        user_groups.format_group_list([group1, group2]),
        "Administrators & Moderators",
        "Two groups should be joined with '&'",
    );
    
    // Test three groups
    assert.equal(
        user_groups.format_group_list([group1, group2, group3]),
        "Administrators, Moderators, & Members",
        "Three groups should be formatted as comma-separated list with '&'",
    );
    
    // Test empty list
    assert.equal(
        user_groups.format_group_list([]),
        "",
        "Empty list should return empty string",
    );
});

run_test("get_supergroups_of_user_group", () => {
    // Test get_supergroups_of_user_group function
    // This function finds all groups that contain the given group as a subgroup
    
    user_groups.init();
    
    const base_group = make_user_group({
        name: "Base",
        id: 1,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    const parent1 = make_user_group({
        name: "Parent1",
        id: 2,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]), // Contains base_group
    });
    
    const parent2 = make_user_group({
        name: "Parent2",
        id: 3,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([1]), // Also contains base_group
    });
    
    const grandparent = make_user_group({
        name: "Grandparent",
        id: 4,
        members: new Set([4]),
        is_system_group: false,
        direct_subgroup_ids: new Set([2]), // Contains parent1, indirectly contains base_group
    });
    
    const unrelated = make_user_group({
        name: "Unrelated",
        id: 5,
        members: new Set([5]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    
    user_groups.initialize({
        realm_user_groups: [base_group, parent1, parent2, grandparent, unrelated],
    });
    
    const supergroups = user_groups.get_supergroups_of_user_group(base_group.id);
    
    // Should find parent1, parent2, and grandparent (but not unrelated)
    assert.equal(supergroups.length, 3, "Should find 3 supergroups");
    assert.deepEqual(
        supergroups.map((g) => g.id).toSorted(),
        [2, 3, 4],
        "Should find direct and indirect parent groups",
    );
    
    // Test group with no supergroups
    const no_supergroups = user_groups.get_supergroups_of_user_group(unrelated.id);
    assert.equal(no_supergroups.length, 0, "Unrelated group should have no supergroups");
});

run_test("check_system_user_group_allowed_for_setting_comprehensive", () => {
    const settings = {
        allow_internet_group: false,
        allow_nobody_group: false,
        allow_everyone_group: false,
        allowed_system_groups: [],
    };

    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:internet", settings, false),
        false,
        "role:internet should be blocked when allow_internet_group is false",
    );
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:nobody", settings, false),
        false,
        "role:nobody should be blocked when allow_nobody_group is false",
    );
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:everyone", settings, false),
        false,
        "role:everyone should be blocked when allow_everyone_group is false",
    );
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:members", settings, false),
        true,
        "role:members should be allowed by default",
    );

    const restricted_settings = {
        allow_internet_group: true,
        allow_nobody_group: true,
        allow_everyone_group: true,
        allowed_system_groups: ["role:administrators"],
    };

    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:administrators", restricted_settings, false),
        true,
        "role:administrators should be allowed when in allowed_system_groups list",
    );
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:members", restricted_settings, false),
        false,
        "role:members should be blocked when not in allowed_system_groups list",
    );

    const base_config = {
        allow_internet_group: true,
        allow_nobody_group: true,
        allow_everyone_group: true,
        allowed_system_groups: [],
    };

    realm.realm_waiting_period_threshold = 0;
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:fullmembers", base_config, true),
        false,
        "role:fullmembers should be blocked when for_new_settings_ui=true and threshold=0",
    );

    realm.realm_waiting_period_threshold = 7;
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:fullmembers", base_config, true),
        true,
        "role:fullmembers should be allowed when for_new_settings_ui=true and threshold>0",
    );

    realm.realm_waiting_period_threshold = 0;
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:fullmembers", base_config, false),
        true,
        "role:fullmembers should be allowed when for_new_settings_ui=false regardless of threshold",
    );

    const nobody_config = {
        allow_internet_group: true,
        allow_nobody_group: true,
        allow_everyone_group: true,
        allowed_system_groups: [],
    };

    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:nobody", nobody_config, false),
        true,
        "role:nobody should be allowed when for_new_settings_ui=false even if allow_nobody_group=true",
    );
    assert.equal(
        user_groups.check_system_user_group_allowed_for_setting("role:nobody", nobody_config, true),
        false,
        "role:nobody should be blocked when for_new_settings_ui=true even if allow_nobody_group=true",
    );
});

run_test("is_setting_group_empty_comprehensive", () => {
    user_groups.init();

    const empty_group = make_user_group({
        name: "empty_group",
        id: 100,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(empty_group);

    const non_empty_group = make_user_group({
        name: "non_empty_group",
        id: 101,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(non_empty_group);

    const group_with_subgroups = make_user_group({
        name: "group_with_subgroups",
        id: 102,
        members: new Set(),
        is_system_group: false,
        direct_subgroup_ids: new Set([101]),
    });
    user_groups.add(group_with_subgroups);

    assert.equal(
        user_groups.is_setting_group_empty(100),
        true,
        "Empty group should return true",
    );

    assert.equal(
        user_groups.is_setting_group_empty(101),
        false,
        "Non-empty group should return false",
    );

    assert.equal(
        user_groups.is_setting_group_empty(102),
        false,
        "Group with non-empty subgroups should return false",
    );

    const empty_setting = {
        direct_members: [],
        direct_subgroups: [100],
    };
    assert.equal(
        user_groups.is_setting_group_empty(empty_setting),
        true,
        "Setting with only empty subgroups should return true",
    );

    const has_members_setting = {
        direct_members: [1],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_setting_group_empty(has_members_setting),
        false,
        "Setting with direct members should return false",
    );

    const has_non_empty_subgroup_setting = {
        direct_members: [],
        direct_subgroups: [101],
    };
    assert.equal(
        user_groups.is_setting_group_empty(has_non_empty_subgroup_setting),
        false,
        "Setting with non-empty subgroups should return false",
    );
});

run_test("is_setting_group_set_to_nobody_group_comprehensive", () => {
    user_groups.init();

    const nobody_group = make_user_group({
        name: "role:nobody",
        id: 200,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(nobody_group);

    const regular_group = make_user_group({
        name: "regular_group",
        id: 201,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(regular_group);

    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(200),
        true,
        "role:nobody group should return true",
    );

    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(201),
        false,
        "Regular group should return false",
    );

    const empty_setting = {
        direct_members: [],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(empty_setting),
        true,
        "Empty setting should return true (equivalent to nobody)",
    );

    const has_members_setting = {
        direct_members: [1],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(has_members_setting),
        false,
        "Setting with members should return false",
    );

    const has_subgroups_setting = {
        direct_members: [],
        direct_subgroups: [201],
    };
    assert.equal(
        user_groups.is_setting_group_set_to_nobody_group(has_subgroups_setting),
        false,
        "Setting with subgroups should return false",
    );
});

run_test("get_all_realm_user_groups_comprehensive", () => {
    user_groups.init();

    const system_group = make_user_group({
        name: "role:administrators",
        id: 300,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    user_groups.add(system_group);

    const internet_group = make_user_group({
        name: "role:internet",
        id: 301,
        members: new Set(),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    user_groups.add(internet_group);

    const active_group = make_user_group({
        name: "active_group",
        id: 302,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    user_groups.add(active_group);

    const deactivated_group = make_user_group({
        name: "deactivated_group",
        id: 303,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    user_groups.add(deactivated_group);

    let all_groups = user_groups.get_all_realm_user_groups();
    assert.equal(all_groups.length, 2, "Should return 2 groups by default");
    assert.ok(all_groups.some(g => g.id === 300), "Should include system_group");
    assert.ok(all_groups.some(g => g.id === 302), "Should include active_group");
    assert.equal(all_groups.some(g => g.id === 301), false, "Should exclude internet_group by default");
    assert.equal(all_groups.some(g => g.id === 303), false, "Should exclude deactivated_group by default");

    all_groups = user_groups.get_all_realm_user_groups(true);
    assert.equal(all_groups.length, 3, "Should return 3 groups when including deactivated");
    assert.ok(all_groups.some(g => g.id === 303), "Should include deactivated_group when flag is true");

    all_groups = user_groups.get_all_realm_user_groups(false, true);
    assert.equal(all_groups.length, 3, "Should return 3 groups when including internet");
    assert.ok(all_groups.some(g => g.id === 301), "Should include internet_group when flag is true");

    all_groups = user_groups.get_all_realm_user_groups(true, true);
    assert.equal(all_groups.length, 4, "Should return all 4 groups when both flags are true");
});

run_test("is_user_in_setting_group_comprehensive", () => {
    user_groups.init();

    const group1 = make_user_group({
        name: "group1",
        id: 400,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(group1);

    const group2 = make_user_group({
        name: "group2",
        id: 401,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(group2);

    assert.equal(
        user_groups.is_user_in_setting_group(400, 1),
        true,
        "User 1 should be in group 400",
    );
    assert.equal(
        user_groups.is_user_in_setting_group(400, 3),
        false,
        "User 3 should not be in group 400",
    );

    const setting_with_direct_members = {
        direct_members: [1, 2],
        direct_subgroups: [],
    };
    assert.equal(
        user_groups.is_user_in_setting_group(setting_with_direct_members, 1),
        true,
        "User 1 should be in setting with direct members",
    );
    assert.equal(
        user_groups.is_user_in_setting_group(setting_with_direct_members, 3),
        false,
        "User 3 should not be in setting with direct members",
    );

    const setting_with_subgroups = {
        direct_members: [],
        direct_subgroups: [401],
    };
    assert.equal(
        user_groups.is_user_in_setting_group(setting_with_subgroups, 3),
        true,
        "User 3 should be in setting via subgroup membership",
    );
    assert.equal(
        user_groups.is_user_in_setting_group(setting_with_subgroups, 1),
        false,
        "User 1 should not be in setting with only group 2 as subgroup",
    );
});

run_test("is_user_in_group_comprehensive", () => {
    user_groups.init();

    const parent_group = make_user_group({
        name: "parent_group",
        id: 500,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set([501]),
    });
    user_groups.add(parent_group);

    const sub_group = make_user_group({
        name: "sub_group",
        id: 501,
        members: new Set([2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(sub_group);

    assert.equal(
        user_groups.is_user_in_group(500, 1),
        true,
        "User 1 should be direct member of group 500",
    );
    assert.equal(
        user_groups.is_user_in_group(501, 2),
        true,
        "User 2 should be direct member of group 501",
    );

    assert.equal(
        user_groups.is_user_in_group(500, 2),
        true,
        "User 2 should be in group 500 via subgroup membership",
    );

    assert.equal(
        user_groups.is_user_in_group(500, 2, true),
        false,
        "User 2 should not be direct member of group 500",
    );
    assert.equal(
        user_groups.is_user_in_group(500, 1, true),
        true,
        "User 1 should be direct member of group 500",
    );

    assert.equal(
        user_groups.is_user_in_group(500, 3),
        false,
        "User 3 should not be in group 500",
    );
});

run_test("user_group_retrieval_functions_comprehensive", () => {
    user_groups.init();

    const test_group = make_user_group({
        name: "TestGroup",
        id: 600,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
    });
    user_groups.add(test_group);

    const group_by_id = user_groups.get_user_group_from_id(600);
    assert.equal(group_by_id.name, "TestGroup", "Should retrieve group by ID");
    assert.equal(group_by_id.id, 600, "Retrieved group should have correct ID");

    const maybe_group = user_groups.maybe_get_user_group_from_id(600);
    assert.equal(maybe_group?.name, "TestGroup", "Should retrieve existing group");

    const maybe_nonexistent = user_groups.maybe_get_user_group_from_id(999);
    assert.equal(maybe_nonexistent, undefined, "Should return undefined for non-existing group");

    const group_by_name = user_groups.get_user_group_from_name("TestGroup");
    assert.equal(group_by_name?.id, 600, "Should retrieve group by name");

    const nonexistent_group = user_groups.get_user_group_from_name("NonExistent");
    assert.equal(nonexistent_group, undefined, "Should return undefined for non-existing group name");

    assert.throws(
        () => user_groups.get_user_group_from_id(999),
        /Unknown group_id in get_user_group_from_id: 999/,
        "Should throw error for non-existing group ID",
    );
});

run_test("realm_has_deactivated_user_groups_comprehensive", () => {
    user_groups.init();

    assert.equal(
        user_groups.realm_has_deactivated_user_groups(),
        false,
        "Should return false when no deactivated groups exist",
    );

    const active_group = make_user_group({
        name: "active_group",
        id: 700,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: false,
    });
    user_groups.add(active_group);

    assert.equal(
        user_groups.realm_has_deactivated_user_groups(),
        false,
        "Should return false when only active groups exist",
    );

    const deactivated_group = make_user_group({
        name: "deactivated_group",
        id: 701,
        members: new Set([1]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });
    user_groups.add(deactivated_group);

    assert.equal(
        user_groups.realm_has_deactivated_user_groups(),
        true,
        "Should return true when deactivated groups exist",
    );
});
