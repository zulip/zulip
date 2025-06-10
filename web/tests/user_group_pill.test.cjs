"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const user_groups = zrequire("user_groups");
const user_group_pill = zrequire("user_group_pill");
const people = zrequire("people");

const user1 = {
    user_id: 10,
    email: "user1@example.com",
    full_name: "User One",
};
people.add_active_user(user1);

const user2 = {
    user_id: 20,
    email: "user2@example.com",
    full_name: "User Two",
};
people.add_active_user(user2);

const user3 = {
    user_id: 30,
    email: "user3@example.com",
    full_name: "User Three",
};
people.add_active_user(user3);

const user4 = {
    user_id: 40,
    email: "user4@example.com",
    full_name: "User Four",
};
people.add_active_user(user4);

const user5 = {
    user_id: 50,
    email: "user5@example.com",
    full_name: "User Five",
};
people.add_active_user(user5);

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
const everyone = {
    name: "role:everyone",
    description: "Everyone",
    id: 103,
    members: [],
    direct_subgroup_ids: [101, 102],
};

const admins_pill = {
    group_id: admins.id,
    group_name: admins.name,
    type: "user_group",
};
const testers_pill = {
    group_id: testers.id,
    group_name: testers.name,
    type: "user_group",
    show_expand_button: false,
};
const everyone_pill = {
    group_id: everyone.id,
    group_name: everyone.name,
    type: "user_group",
    // While we can programmatically set the user count below,
    // calculating it would almost mimic the entire display function
    // here, reducing the usefulness of the test.
};

const groups = [admins, testers, everyone];
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
    test_create_item("role:everyone", [], everyone_pill);
});

run_test("get_stream_id", () => {
    assert.equal(user_group_pill.get_group_name_from_item(admins_pill), admins.name);
});

run_test("get_user_ids", () => {
    let items = [admins_pill, testers_pill];
    const widget = {items: () => items};

    let user_ids = user_group_pill.get_user_ids(widget);
    assert.deepEqual(user_ids, [10, 20, 30, 40, 50]);

    // Test whether subgroup members are included or not.
    items = [everyone_pill];
    user_ids = user_group_pill.get_user_ids(widget);
    assert.deepEqual(user_ids, [10, 20, 30, 40, 50]);

    // Deactivated users should be excluded.
    people.deactivate(user5);
    user_ids = user_group_pill.get_user_ids(widget);
    assert.deepEqual(user_ids, [10, 20, 30, 40]);
    people.add_active_user(user5);
});

run_test("get_group_ids", () => {
    const items = [admins_pill, everyone_pill];
    const widget = {items: () => items};

    // Subgroups should not be part of the results, we use `everyone_pill` to test that.
    const group_ids = user_group_pill.get_group_ids(widget);
    assert.deepEqual(group_ids, [101, 103]);
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

run_test("generate_pill_html", () => {
    assert.deepEqual(
        user_group_pill.generate_pill_html(testers_pill),
        "<div class='pill 'data-user-group-id=\"102\" tabindex=0>\n" +
            '    <span class="pill-label">\n' +
            '        <span class="pill-value">\n' +
            "            Testers\n" +
            '        </span>&nbsp;<span class="group-members-count">(4)</span></span>\n' +
            '    <div class="exit">\n' +
            '        <a role="button" class="zulip-icon zulip-icon-close pill-close-button"></a>\n' +
            "    </div>\n" +
            "</div>\n",
    );
});
