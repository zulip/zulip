"use strict";

const assert = require("node:assert/strict");

const {make_user_group} = require("./lib/example_group.cjs");
const {make_realm} = require("./lib/example_realm.cjs");
const {server_supported_permission_settings} = require("./lib/example_settings.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const group_permission_settings = zrequire("group_permission_settings");
const user_groups = zrequire("user_groups");
const {initialize_user_settings} = zrequire("user_settings");
const {set_realm, set_current_user} = zrequire("state_data");

const realm = make_realm();
set_realm(realm);
initialize_user_settings({user_settings: {default_language: "en"}});

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

function set_up_system_groups_for_test() {
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

    return {nobody, owners, admins, moderators, members, everyone, full_members, internet};
}

run_test("get_realm_user_groups_for_dropdown_list_widget", ({override}) => {
    const {nobody, owners, admins, moderators, members, everyone, full_members, internet} =
        set_up_system_groups_for_test();

    const students = make_user_group({
        description: "Students group",
        name: "Students",
        id: 9,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
    });

    override(realm, "server_supported_permission_settings", server_supported_permission_settings);

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

run_test("get_potential_subgroups", ({override}) => {
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
    const full_members = make_user_group({
        name: "role:fullmembers",
        id: 6,
        members: new Set([5, 6, 7, 8, 9]),
        is_system_group: true,
        direct_subgroup_ids: new Set(),
    });

    user_groups.initialize({
        realm_user_groups: [admins, all, students, teachers, science, full_members],
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

    override(realm, "realm_waiting_period_threshold", 100);
    assert.deepEqual(get_potential_subgroup_ids(all.id), [
        teachers.id,
        science.id,
        full_members.id,
    ]);
    assert.deepEqual(get_potential_subgroup_ids(science.id), [
        admins.id,
        all.id,
        students.id,
        teachers.id,
        full_members.id,
    ]);

    override(realm, "realm_waiting_period_threshold", 0);

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
    override(realm, "server_supported_permission_settings", server_supported_permission_settings);

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

run_test("get_all_realm_user_groups", ({override}) => {
    const {nobody, owners, admins, moderators, members, everyone, full_members, internet} =
        set_up_system_groups_for_test();

    const students = make_user_group({
        description: "Students group",
        name: "Students",
        id: 9,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
    });

    const deactivated = make_user_group({
        description: "Deactivated group",
        name: "Deactivated",
        id: 10,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set(),
        deactivated: true,
    });

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
            deactivated,
        ],
    });

    override(realm, "server_supported_permission_settings", server_supported_permission_settings);
    override(realm, "realm_waiting_period_threshold", 0);
    // By default deactivated groups and internet group is not included.
    // Full members group is not included since waiting period is 0.
    let expected_groups_list = [nobody, owners, admins, moderators, members, everyone, students];

    assert.deepEqual(user_groups.get_all_realm_user_groups(), expected_groups_list);

    // deactivated group is included if include_deactivated_group is true.
    expected_groups_list = [
        nobody,
        owners,
        admins,
        moderators,
        members,
        everyone,
        students,
        deactivated,
    ];
    assert.deepEqual(user_groups.get_all_realm_user_groups(true), expected_groups_list);

    // internet group is included if include_internet_group is true.
    expected_groups_list = [
        nobody,
        owners,
        admins,
        moderators,
        members,
        everyone,
        internet,
        students,
    ];
    assert.deepEqual(user_groups.get_all_realm_user_groups(false, true), expected_groups_list);

    // Full members group is included by default if waiting period
    // is not 0.
    override(realm, "realm_waiting_period_threshold", 10);
    expected_groups_list = [
        nobody,
        owners,
        admins,
        moderators,
        members,
        everyone,
        full_members,
        students,
    ];
    assert.deepEqual(user_groups.get_all_realm_user_groups(), expected_groups_list);

    // Full members group is included even if waiting period is 0
    // if force_include_full_members_group is true.
    override(realm, "realm_waiting_period_threshold", 0);
    assert.deepEqual(
        user_groups.get_all_realm_user_groups(false, false, true),
        expected_groups_list,
    );
});

run_test("update_group_permission_settings", () => {
    user_groups.init();
    const group = make_user_group({
        name: "Test Group",
        id: 1,
        members: [1],
        is_system_group: false,
        direct_subgroup_ids: [],
        can_add_members_group: 1,
        can_join_group: 1,
        can_leave_group: 1,
        can_manage_group: 1,
        can_mention_group: 1,
        can_remove_members_group: 1,
    });
    user_groups.add(group);
    const stored_group = user_groups.get_user_group_from_id(group.id);

    user_groups.update({group_id: group.id, data: {can_add_members_group: 2}}, stored_group);
    assert.equal(user_groups.get_user_group_from_id(group.id).can_add_members_group, 2);

    user_groups.update({group_id: group.id, data: {can_mention_group: 3}}, stored_group);
    assert.equal(user_groups.get_user_group_from_id(group.id).can_mention_group, 3);

    user_groups.update({group_id: group.id, data: {can_manage_group: 4}}, stored_group);
    assert.equal(user_groups.get_user_group_from_id(group.id).can_manage_group, 4);

    user_groups.update({group_id: group.id, data: {can_join_group: 5}}, stored_group);
    assert.equal(user_groups.get_user_group_from_id(group.id).can_join_group, 5);

    user_groups.update({group_id: group.id, data: {can_leave_group: 6}}, stored_group);
    assert.equal(user_groups.get_user_group_from_id(group.id).can_leave_group, 6);

    user_groups.update({group_id: group.id, data: {can_remove_members_group: 7}}, stored_group);
    assert.equal(user_groups.get_user_group_from_id(group.id).can_remove_members_group, 7);
});

run_test("realm_has_deactivated_user_groups", () => {
    user_groups.init();
    const active = make_user_group({
        name: "Active",
        id: 1,
        members: [1],
        is_system_group: false,
        direct_subgroup_ids: [],
        deactivated: false,
    });
    user_groups.add(active);
    assert.ok(!user_groups.realm_has_deactivated_user_groups());

    const deactivated = make_user_group({
        name: "Deactivated",
        id: 2,
        members: [2],
        is_system_group: false,
        direct_subgroup_ids: [],
        deactivated: true,
    });
    user_groups.add(deactivated);
    assert.ok(user_groups.realm_has_deactivated_user_groups());
});

run_test("get_system_groups_list", ({override}) => {
    user_groups.init();
    const {nobody, owners, admins, moderators, members, everyone, full_members, internet} =
        set_up_system_groups_for_test();

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
        ],
    });

    override(realm, "realm_waiting_period_threshold", 0);
    let group_list = user_groups.get_system_groups_list();
    // internet and nobody are always excluded; fullmembers excluded when threshold is 0.
    // system_user_groups_list order after filter + toReversed:
    // [owners, administrators, moderators, members, everyone]
    assert.deepEqual(
        group_list.map((g) => ({id: g.id, name: g.name})),
        [
            {id: owners.id, name: "translated: Owners"},
            {id: admins.id, name: "translated: Administrators"},
            {id: moderators.id, name: "translated: Moderators"},
            {id: members.id, name: "translated: Everyone except guests"},
            {id: everyone.id, name: "translated: Everyone including guests"},
        ],
    );

    override(realm, "realm_waiting_period_threshold", 10);
    group_list = user_groups.get_system_groups_list();
    // fullmembers is included when threshold > 0.
    assert.deepEqual(
        group_list.map((g) => ({id: g.id, name: g.name})),
        [
            {id: owners.id, name: "translated: Owners"},
            {id: admins.id, name: "translated: Administrators"},
            {id: moderators.id, name: "translated: Moderators"},
            {id: full_members.id, name: "translated: Full members"},
            {id: members.id, name: "translated: Everyone except guests"},
            {id: everyone.id, name: "translated: Everyone including guests"},
        ],
    );
});

run_test("get_user_groups_allowed_to_mention", () => {
    user_groups.init();
    set_current_user({user_id: 5});

    // User 5 is listed as a direct member of the can_mention_group for mentionable.
    const mentionable = make_user_group({
        name: "Mentionable",
        id: 1,
        members: [1, 2],
        is_system_group: false,
        direct_subgroup_ids: [],
        can_mention_group: {direct_members: [5], direct_subgroups: []},
    });
    // User 5 is not in the can_mention_group for restricted.
    const restricted = make_user_group({
        name: "Restricted",
        id: 2,
        members: [6, 7],
        is_system_group: false,
        direct_subgroup_ids: [],
        can_mention_group: {direct_members: [6, 7], direct_subgroups: []},
    });

    user_groups.initialize({realm_user_groups: [mentionable, restricted]});

    const result = user_groups.get_user_groups_allowed_to_mention();
    assert.equal(result.length, 1);
    assert.equal(result[0].id, mentionable.id);

    user_groups.init();
});

run_test("is_empty_group", () => {
    user_groups.init();
    const empty_group = make_user_group({
        name: "Empty",
        id: 1,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const non_empty_group = make_user_group({
        name: "NonEmpty",
        id: 2,
        members: [1],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const empty_subgroup = make_user_group({
        name: "EmptySubgroup",
        id: 3,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const group_with_empty_sub = make_user_group({
        name: "GroupWithEmptySub",
        id: 4,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [3],
    });
    const group_with_nonempty_sub = make_user_group({
        name: "GroupWithNonEmptySub",
        id: 5,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [2],
    });
    // Three-level chain: root → child → grandchild; all empty.
    const grandchild = make_user_group({
        name: "Grandchild",
        id: 10,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const child = make_user_group({
        name: "Child",
        id: 11,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [10],
    });
    const root = make_user_group({
        name: "Root",
        id: 12,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [11],
    });

    user_groups.add(empty_group);
    user_groups.add(non_empty_group);
    user_groups.add(empty_subgroup);
    user_groups.add(group_with_empty_sub);
    user_groups.add(group_with_nonempty_sub);
    user_groups.add(grandchild);
    user_groups.add(child);
    user_groups.add(root);

    assert.ok(user_groups.is_empty_group(empty_group.id));
    assert.ok(!user_groups.is_empty_group(non_empty_group.id));
    assert.ok(user_groups.is_empty_group(group_with_empty_sub.id));
    assert.ok(!user_groups.is_empty_group(group_with_nonempty_sub.id));

    blueslip.expect("error", "Could not find user group");
    assert.ok(!user_groups.is_empty_group(9999));

    user_groups.add_subgroups(group_with_empty_sub.id, [9999]);
    blueslip.expect("error", "Could not find subgroup");
    assert.ok(!user_groups.is_empty_group(group_with_empty_sub.id));

    // Subgroups discovered during BFS are themselves enqueued, verifying
    // the traversal loop body executes more than one iteration.
    assert.ok(user_groups.is_empty_group(root.id));
});

run_test("is_setting_group_empty", () => {
    user_groups.init();
    const empty_group = make_user_group({
        name: "Empty",
        id: 1,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const non_empty_group = make_user_group({
        name: "NonEmpty",
        id: 2,
        members: [1],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const empty_subgroup = make_user_group({
        name: "EmptySubgroup",
        id: 3,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });

    user_groups.add(empty_group);
    user_groups.add(non_empty_group);
    user_groups.add(empty_subgroup);

    assert.ok(user_groups.is_setting_group_empty(empty_group.id));
    assert.ok(!user_groups.is_setting_group_empty(non_empty_group.id));

    assert.ok(user_groups.is_setting_group_empty({direct_members: [], direct_subgroups: []}));
    assert.ok(!user_groups.is_setting_group_empty({direct_members: [1], direct_subgroups: []}));
    assert.ok(
        !user_groups.is_setting_group_empty({
            direct_members: [],
            direct_subgroups: [non_empty_group.id],
        }),
    );
    assert.ok(
        user_groups.is_setting_group_empty({
            direct_members: [],
            direct_subgroups: [empty_subgroup.id],
        }),
    );
});

run_test("is_setting_group_set_to_nobody_group", () => {
    user_groups.init();
    const empty_group = make_user_group({
        name: "Empty",
        id: 1,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const nobody = make_user_group({
        name: "role:nobody",
        id: 2,
        members: [],
        is_system_group: true,
        direct_subgroup_ids: [],
    });

    user_groups.add(empty_group);
    user_groups.add(nobody);

    assert.ok(user_groups.is_setting_group_set_to_nobody_group(nobody.id));
    assert.ok(!user_groups.is_setting_group_set_to_nobody_group(empty_group.id));

    assert.ok(
        user_groups.is_setting_group_set_to_nobody_group({
            direct_members: [],
            direct_subgroups: [],
        }),
    );
    assert.ok(
        !user_groups.is_setting_group_set_to_nobody_group({
            direct_members: [1],
            direct_subgroups: [],
        }),
    );
});

run_test("get_direct_subgroups_of_group", () => {
    user_groups.init();
    const sub_a = make_user_group({
        name: "SubA",
        id: 1,
        members: [1],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const sub_b = make_user_group({
        name: "SubB",
        id: 2,
        members: [2],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const parent = make_user_group({
        name: "Parent",
        id: 3,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [1, 2],
    });
    user_groups.add(sub_a);
    user_groups.add(sub_b);
    const parent_group = user_groups.add(parent);

    const direct_subgroups = user_groups.get_direct_subgroups_of_group(parent_group);
    assert.equal(direct_subgroups.length, 2);
    assert.deepEqual(direct_subgroups.map((g) => g.id).toSorted(), [sub_a.id, sub_b.id]);
});

run_test("get_supergroups_of_user_group", () => {
    user_groups.init();
    const base = make_user_group({
        name: "Base",
        id: 1,
        members: [1],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const parent_a = make_user_group({
        name: "ParentA",
        id: 2,
        members: [2],
        is_system_group: false,
        direct_subgroup_ids: [1],
    });
    const parent_b = make_user_group({
        name: "ParentB",
        id: 3,
        members: [3],
        is_system_group: false,
        direct_subgroup_ids: [1],
    });
    const unrelated = make_user_group({
        name: "Unrelated",
        id: 4,
        members: [4],
        is_system_group: false,
        direct_subgroup_ids: [],
    });

    user_groups.initialize({realm_user_groups: [base, parent_a, parent_b, unrelated]});

    assert.deepEqual(
        user_groups
            .get_supergroups_of_user_group(base.id)
            .map((g) => g.id)
            .toSorted(),
        [parent_a.id, parent_b.id],
    );
    assert.deepEqual(user_groups.get_supergroups_of_user_group(unrelated.id), []);
});

run_test("is_group_larger_than", () => {
    user_groups.init();
    const small = user_groups.add(
        make_user_group({
            name: "Small",
            id: 1,
            members: [1, 2],
            is_system_group: false,
            direct_subgroup_ids: [],
        }),
    );
    user_groups.add(
        make_user_group({
            name: "Sub",
            id: 2,
            members: [3, 4, 5],
            is_system_group: false,
            direct_subgroup_ids: [],
        }),
    );
    const with_sub = user_groups.add(
        make_user_group({
            name: "WithSub",
            id: 3,
            members: [1, 2],
            is_system_group: false,
            direct_subgroup_ids: [2],
        }),
    );

    // small has 2 members: threshold 1 → larger; threshold 2 → not larger (2 > 2 is false)
    assert.ok(user_groups.is_group_larger_than(small, 1));
    assert.ok(!user_groups.is_group_larger_than(small, 2));

    // with_sub: members [1,2] + sub [3,4,5] = 5 distinct; threshold 4 → larger; threshold 5 → not
    assert.ok(user_groups.is_group_larger_than(with_sub, 4));
    assert.ok(!user_groups.is_group_larger_than(with_sub, 5));

    // get_recursive_subgroups returns undefined when a subgroup is missing → return false.
    // Threshold must exceed small.members.size (2) so the early-return branch is not taken.
    user_groups.add_subgroups(small.id, [9999]);
    const small_group = user_groups.get_user_group_from_id(small.id);
    blueslip.expect("error", "Could not find subgroup");
    assert.ok(!user_groups.is_group_larger_than(small_group, 100));
});

run_test("check_group_can_be_subgroup", () => {
    user_groups.init();
    const active = user_groups.add(
        make_user_group({
            name: "Active",
            id: 1,
            members: [1],
            is_system_group: false,
            direct_subgroup_ids: [],
            deactivated: false,
        }),
    );
    const target = user_groups.add(
        make_user_group({
            name: "Target",
            id: 2,
            members: [2],
            is_system_group: false,
            direct_subgroup_ids: [],
            deactivated: false,
        }),
    );
    const deactivated_group = user_groups.add(
        make_user_group({
            name: "Deactivated",
            id: 3,
            members: [3],
            is_system_group: false,
            direct_subgroup_ids: [],
            deactivated: true,
        }),
    );

    assert.ok(user_groups.check_group_can_be_subgroup(active, target));
    assert.ok(!user_groups.check_group_can_be_subgroup(deactivated_group, target));
    assert.ok(!user_groups.check_group_can_be_subgroup(target, target));
});

run_test("is_user_in_any_group", () => {
    user_groups.init();
    const group_a = make_user_group({
        name: "GroupA",
        id: 1,
        members: [1, 2],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const group_b = make_user_group({
        name: "GroupB",
        id: 2,
        members: [3],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const sub = make_user_group({
        name: "Sub",
        id: 3,
        members: [4],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const group_c = make_user_group({
        name: "GroupC",
        id: 4,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [3],
    });

    user_groups.add(group_a);
    user_groups.add(group_b);
    user_groups.add(sub);
    user_groups.add(group_c);

    assert.ok(user_groups.is_user_in_any_group([group_a.id, group_b.id], 1));
    assert.ok(user_groups.is_user_in_any_group([group_a.id, group_b.id], 3));
    assert.ok(!user_groups.is_user_in_any_group([group_a.id, group_b.id], 5));

    // user 4 is in group_c via sub subgroup, but not a direct member of group_c
    assert.ok(user_groups.is_user_in_any_group([group_c.id], 4));
    assert.ok(!user_groups.is_user_in_any_group([group_c.id], 4, true));

    user_groups.init();
});

run_test("format_group_list", () => {
    const group_a = make_user_group({
        name: "Alpha",
        id: 1,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const group_b = make_user_group({
        name: "Beta",
        id: 2,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const group_c = make_user_group({
        name: "Gamma",
        id: 3,
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
    });

    const result = user_groups.format_group_list([group_a, group_b, group_c]);
    assert.equal(result, "Alpha, Beta, & Gamma");

    const single = user_groups.format_group_list([group_a]);
    assert.equal(single, "Alpha");
});

run_test("get_user_ids_in_setting_group", () => {
    user_groups.init();
    const group_a = make_user_group({
        name: "GroupA",
        id: 1,
        members: [1, 2],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const sub = make_user_group({
        name: "Sub",
        id: 2,
        members: [3],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const group_b = make_user_group({
        name: "GroupB",
        id: 3,
        members: [4],
        is_system_group: false,
        direct_subgroup_ids: [2],
    });

    user_groups.add(group_a);
    user_groups.add(sub);
    user_groups.add(group_b);

    // Number form: collects all recursive members of the referenced group.
    assert.deepEqual(user_groups.get_user_ids_in_setting_group(group_a.id), new Set([1, 2]));
    assert.deepEqual(user_groups.get_user_ids_in_setting_group(group_b.id), new Set([3, 4]));

    // Anonymous group form: direct_members + recursive members of each direct_subgroup.
    assert.deepEqual(
        user_groups.get_user_ids_in_setting_group({
            direct_members: [5, 6],
            direct_subgroups: [group_a.id],
        }),
        new Set([1, 2, 5, 6]),
    );

    // Unknown group in direct_subgroups: blueslip error, rest of collection continues.
    blueslip.expect("error", "Could not find user group");
    assert.deepEqual(
        user_groups.get_user_ids_in_setting_group({
            direct_members: [7],
            direct_subgroups: [9999],
        }),
        new Set([7]),
    );
});

run_test("check_system_user_group_allowed_for_setting", ({override}) => {
    const base_config = {
        require_system_group: false,
        allow_internet_group: false,
        allow_nobody_group: true,
        allow_everyone_group: true,
        default_group_name: "role:members",
        default_for_system_groups: null,
        allowed_system_groups: [],
    };

    // role:internet blocked when allow_internet_group is false
    assert.ok(
        !user_groups.check_system_user_group_allowed_for_setting(
            "role:internet",
            base_config,
            false,
        ),
    );
    // role:internet allowed when allow_internet_group is true
    assert.ok(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:internet",
            {...base_config, allow_internet_group: true},
            false,
        ),
    );

    // role:nobody blocked when allow_nobody_group is false
    assert.ok(
        !user_groups.check_system_user_group_allowed_for_setting(
            "role:nobody",
            {...base_config, allow_nobody_group: false},
            false,
        ),
    );
    // role:nobody allowed when allow_nobody_group is true and not new settings ui
    assert.ok(
        user_groups.check_system_user_group_allowed_for_setting("role:nobody", base_config, false),
    );
    // role:nobody blocked by for_new_settings_ui even when allow_nobody_group is true
    assert.ok(
        !user_groups.check_system_user_group_allowed_for_setting("role:nobody", base_config, true),
    );

    // role:everyone blocked when allow_everyone_group is false
    assert.ok(
        !user_groups.check_system_user_group_allowed_for_setting(
            "role:everyone",
            {...base_config, allow_everyone_group: false},
            false,
        ),
    );
    // role:everyone allowed when allow_everyone_group is true
    assert.ok(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:everyone",
            base_config,
            false,
        ),
    );

    // allowed_system_groups filter: group not in list is blocked
    assert.ok(
        !user_groups.check_system_user_group_allowed_for_setting(
            "role:administrators",
            {...base_config, allowed_system_groups: ["role:members"]},
            false,
        ),
    );
    // allowed_system_groups filter: group in list is allowed
    assert.ok(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:members",
            {...base_config, allowed_system_groups: ["role:members"]},
            false,
        ),
    );

    // role:fullmembers blocked when for_new_settings_ui and threshold is 0
    override(realm, "realm_waiting_period_threshold", 0);
    assert.ok(
        !user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            base_config,
            true,
        ),
    );
    // role:fullmembers allowed when for_new_settings_ui is false regardless of threshold
    assert.ok(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            base_config,
            false,
        ),
    );
    // role:fullmembers allowed when for_new_settings_ui but threshold > 0
    override(realm, "realm_waiting_period_threshold", 10);
    assert.ok(
        user_groups.check_system_user_group_allowed_for_setting(
            "role:fullmembers",
            base_config,
            true,
        ),
    );
});

run_test("is_subgroup_of_target_group_bad_subgroup", () => {
    user_groups.init();
    const leaf = make_user_group({
        name: "Leaf",
        id: 1,
        members: [1],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const mid = make_user_group({
        name: "Mid",
        id: 2,
        members: [2],
        is_system_group: false,
        direct_subgroup_ids: [1],
    });
    const top = make_user_group({
        name: "Top",
        id: 3,
        members: [3],
        is_system_group: false,
        direct_subgroup_ids: [2],
    });
    user_groups.add(leaf);
    user_groups.add(mid);
    user_groups.add(top);

    assert.ok(user_groups.is_subgroup_of_target_group(top.id, leaf.id));

    // Adding an unknown subgroup to top causes get_recursive_subgroups to return undefined.
    user_groups.add_subgroups(top.id, [9999]);
    blueslip.expect("error", "Could not find subgroup");
    assert.ok(!user_groups.is_subgroup_of_target_group(top.id, leaf.id));
});

run_test("get_associated_subgroups_bad_subgroup", () => {
    // Verify that get_associated_subgroups returns [] when get_recursive_subgroups
    // returns undefined due to a missing subgroup reference.
    user_groups.init();
    const sub = make_user_group({
        name: "Sub",
        id: 1,
        members: [10],
        is_system_group: false,
        direct_subgroup_ids: [],
    });
    const group = make_user_group({
        name: "Group",
        id: 2,
        members: [20],
        is_system_group: false,
        direct_subgroup_ids: [1, 9999],
    });
    user_groups.add(sub);
    const group_obj = user_groups.add(group);

    blueslip.expect("error", "Could not find subgroup");
    assert.deepEqual(user_groups.get_associated_subgroups(group_obj, 10), []);
});
