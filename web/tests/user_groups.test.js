"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");

const user_groups = zrequire("user_groups");

run_test("user_groups", () => {
    const students = {
        description: "Students group",
        name: "Students",
        id: 0,
        members: new Set([1, 2]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5]),
        can_mention_group: 2,
    };

    const params = {};
    params.realm_user_groups = [students];
    const user_id_not_in_any_group = 0;
    const user_id_part_of_a_group = 2;

    user_groups.initialize(params);
    assert.deepEqual(user_groups.get_user_group_from_id(students.id), students);

    const admins = {
        name: "Admins",
        description: "foo",
        id: 1,
        members: new Set([3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([]),
        can_mention_group: 2,
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([1, 2, 3]),
        is_system_group: false,
        direct_subgroup_ids: new Set([4, 5, 6]),
        can_mention_group: 1,
    };

    user_groups.add(admins);
    assert.deepEqual(user_groups.get_user_group_from_id(admins.id), admins);

    const update_name_event = {
        group_id: admins.id,
        data: {
            name: "new admins",
        },
    };
    user_groups.update(update_name_event);
    assert.equal(user_groups.get_user_group_from_id(admins.id).name, "new admins");

    const update_des_event = {
        group_id: admins.id,
        data: {
            description: "administer",
        },
    };
    user_groups.update(update_des_event);
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
    assert.equal(user_groups.get_user_group_from_name(admins.name).id, 1);

    user_groups.add(all);
    const user_groups_array = user_groups.get_realm_user_groups();
    assert.equal(user_groups_array.length, 2);
    assert.equal(user_groups_array[1].name, "Everyone");
    assert.equal(user_groups_array[0].name, "new admins");

    const groups_of_users = user_groups.get_user_groups_of_user(user_id_part_of_a_group);
    assert.equal(groups_of_users.length, 1);
    assert.equal(groups_of_users[0].name, "Everyone");

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

    blueslip.expect("error", "Could not find user group");
    assert.equal(user_groups.is_user_in_group(1111, 3), false);

    user_groups.add_subgroups(foo.id, [9999]);
    blueslip.expect("error", "Could not find subgroup");
    assert.equal(user_groups.is_user_in_group(admins.id, 6), false);
});

run_test("get_realm_user_groups_for_dropdown_list_widget", () => {
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

    const expected_groups_list = [
        {name: "translated: Admins, moderators, members and guests", unique_id: 6},
        {name: "translated: Admins, moderators and members", unique_id: 5},
        {name: "translated: Admins, moderators and full members", unique_id: 7},
        {name: "translated: Admins and moderators", unique_id: 4},
        {name: "translated: Admins", unique_id: 3},
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
        user_groups.get_realm_user_groups_for_dropdown_list_widget("can_remove_subscribers_group"),
        expected_groups_list,
    );

    assert.throws(
        () => user_groups.get_realm_user_groups_for_dropdown_list_widget("invalid_setting"),
        {
            name: "Error",
            message: "Invalid setting: invalid_setting",
        },
    );
});
