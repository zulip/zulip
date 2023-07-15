"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const user_groups = zrequire("user_groups");
const user_group_pill = zrequire("user_group_pill");

const admins = {
    name: "Admins",
    description: "foo",
    id: 101,
    members: [10, 20],
};
const testers = {
    name: "Testers",
    description: "bar",
    id: 102,
    members: [20, 50, 30, 40],
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

run_test("get_user_ids", () => {
    const items = [admins_pill, testers_pill];
    const widget = {items: () => items};

    const user_ids = user_group_pill.get_user_ids(widget);
    assert.deepEqual(user_ids, [10, 20, 30, 40, 50]);
});

run_test("get_group_ids", () => {
    const items = [admins_pill, testers_pill];
    const widget = {items: () => items};

    const group_ids = user_group_pill.get_group_ids(widget);
    assert.deepEqual(group_ids, [101, 102]);
});

run_test("append_user_group", () => {
    const items = [admins_pill];
    const widget = {
        appendValidatedData(group) {
            assert.deepEqual(group, testers_pill);
            items.push(testers_pill);
        },
        clear_text() {},
    };

    const group = {
        ...testers,
        members: new Set(testers.members),
    };
    user_group_pill.append_user_group(group, widget);
    assert.deepEqual(items, [admins_pill, testers_pill]);
});
