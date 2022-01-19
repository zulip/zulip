"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");

const user_groups = zrequire("user_groups");

run_test("user_groups", () => {
    const students = {
        description: "Students group",
        name: "Students",
        id: 0,
        members: new Set([1, 2]),
        is_system_group: false,
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
    };
    const all = {
        name: "Everyone",
        id: 2,
        members: new Set([1, 2, 3]),
        is_system_group: false,
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

    assert.ok(!user_groups.is_member_of(admins.id, 4));
    assert.ok(user_groups.is_member_of(admins.id, 3));

    user_groups.add_members(all.id, [5, 4]);
    assert.deepEqual(user_groups.get_user_group_from_id(all.id).members, new Set([1, 2, 3, 5, 4]));

    user_groups.remove_members(all.id, [1, 4]);
    assert.deepEqual(user_groups.get_user_group_from_id(all.id).members, new Set([2, 3, 5]));

    assert.ok(user_groups.is_user_group(admins));
    const object = {
        name: "core",
        id: 3,
    };
    assert.ok(!user_groups.is_user_group(object));

    user_groups.init();
    assert.equal(user_groups.get_realm_user_groups().length, 0);

    blueslip.expect("error", "Could not find user group with ID -1");
    assert.equal(user_groups.is_member_of(-1, 15), false);

    blueslip.expect("error", "Could not find user group with ID -9999", 2);
    user_groups.add_members(-9999);
    user_groups.remove_members(-9999);
});
