"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const user_groups = zrequire("user_groups");
const user_group_pill = zrequire("user_group_pill");

const admins = {
    name: "Admins",
    description: "foo",
    id: 1,
    members: [10, 20],
};
const testers = {
    name: "Testers",
    description: "bar",
    id: 2,
    members: [20, 30, 40],
};

const admins_pill = {
    id: admins.id,
    group_name: admins.name,
    type: "user_group",
    display_value: admins.name + ": " + admins.members.length + " users",
};
const testers_pill = {
    id: testers.id,
    group_name: testers.name,
    type: "user_group",
    display_value: testers.name + ": " + testers.members.length + " users",
};

const groups = [admins, testers];
for (const group of groups) {
    user_groups.add(group);
}

run_test("create_item", () => {
    function test_create_item(group_name, current_items, expected_item) {
        const item = user_group_pill.create_item_from_group_name(group_name, current_items);
        assert.deepEqual(item, expected_item);
    }

    test_create_item(" admins ", [], admins_pill);
    test_create_item("admins", [testers_pill], admins_pill);
    test_create_item("admins", [admins_pill], undefined);
    test_create_item("unknown", [], undefined);
});

run_test("get_stream_id", () => {
    assert.equal(user_group_pill.get_group_name_from_item(admins_pill), admins.name);
});
