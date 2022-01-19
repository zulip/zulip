"use strict";

const {strict: assert} = require("assert");

const {mock_esm, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const narrow_state = mock_esm("../../static/js/narrow_state");
const pm_list_dom = mock_esm("../../static/js/pm_list_dom");
const unread = mock_esm("../../static/js/unread");
const vdom = mock_esm("../../static/js/vdom", {
    render: () => "fake-dom-for-pm-list",
});

mock_esm("../../static/js/stream_popover", {
    hide_topic_popover() {},
});
mock_esm("../../static/js/ui", {
    get_content_element: (element) => element,
});

const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
const pm_list = zrequire("pm_list");

const alice = {
    email: "alice@zulip.com",
    user_id: 101,
    full_name: "Alice",
};
const bob = {
    email: "bob@zulip.com",
    user_id: 102,
    full_name: "Bob",
};
const me = {
    email: "me@zulip.com",
    user_id: 103,
    full_name: "Me Myself",
};
const bot_test = {
    email: "outgoingwebhook@zulip.com",
    user_id: 314,
    full_name: "Outgoing webhook",
    is_admin: false,
    is_bot: true,
};
people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(me);
people.add_active_user(bot_test);
people.initialize_current_user(me.user_id);

function test(label, f) {
    run_test(label, ({override, override_rewire}) => {
        pm_conversations.clear_for_testing();
        pm_list.clear_for_testing();
        f({override, override_rewire});
    });
}

test("close", () => {
    let collapsed;
    $("#private-container").empty = () => {
        collapsed = true;
    };
    pm_list.close();
    assert.ok(collapsed);
});

test("build_private_messages_list", ({override}) => {
    const timestamp = 0;
    pm_conversations.recent.insert([101, 102], timestamp);

    let num_unread_for_person = 1;
    override(unread, "num_unread_for_person", () => num_unread_for_person);

    let pm_data;

    override(pm_list_dom, "pm_ul", (data) => {
        pm_data = data;
    });

    override(narrow_state, "filter", () => {});
    pm_list._build_private_messages_list();

    const expected_data = [
        {
            recipients: "Alice, Bob",
            user_ids_string: "101,102",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/pm-with/101,102-group",
            user_circle_class: "user_circle_fraction",
            is_group: true,
        },
    ];

    assert.deepEqual(pm_data, expected_data);

    num_unread_for_person = 0;
    pm_list._build_private_messages_list();
    expected_data[0].unread = 0;
    expected_data[0].is_zero = true;
    assert.deepEqual(pm_data, expected_data);

    pm_list._build_private_messages_list();
    assert.deepEqual(pm_data, expected_data);
});

test("build_private_messages_list_bot", ({override}) => {
    const timestamp = 0;
    pm_conversations.recent.insert([101, 102], timestamp);
    pm_conversations.recent.insert([314], timestamp);

    override(unread, "num_unread_for_person", () => 1);

    let pm_data;
    override(pm_list_dom, "pm_ul", (data) => {
        pm_data = data;
    });

    override(narrow_state, "filter", () => {});

    pm_list._build_private_messages_list();
    const expected_data = [
        {
            recipients: "Outgoing webhook",
            user_ids_string: "314",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/pm-with/314-outgoingwebhook",
            user_circle_class: "user_circle_green",
            is_group: false,
        },
        {
            recipients: "Alice, Bob",
            user_ids_string: "101,102",
            unread: 1,
            is_zero: false,
            is_active: false,
            url: "#narrow/pm-with/101,102-group",
            user_circle_class: "user_circle_fraction",
            is_group: true,
        },
    ];

    assert.deepEqual(pm_data, expected_data);
});

test("update_dom_with_unread_counts", ({override}) => {
    let counts;

    override(narrow_state, "active", () => true);

    const total_count = $.create("total-count-stub");
    const private_li = $(".top_left_private_messages .private_messages_header");
    private_li.set_find_results(".unread_count", total_count);

    counts = {
        private_message_count: 10,
    };

    pm_list.update_dom_with_unread_counts(counts);
    assert.equal(total_count.text(), "10");
    assert.ok(total_count.visible());

    counts = {
        private_message_count: 0,
    };

    pm_list.update_dom_with_unread_counts(counts);
    assert.equal(total_count.text(), "");
    assert.ok(!total_count.visible());
});

test("get_active_user_ids_string", ({override}) => {
    let active_filter;

    override(narrow_state, "filter", () => active_filter);

    assert.equal(pm_list.get_active_user_ids_string(), undefined);

    function set_filter_result(emails) {
        active_filter = {
            operands: (operand) => {
                assert.equal(operand, "pm-with");
                return emails;
            },
        };
    }

    set_filter_result([]);
    assert.equal(pm_list.get_active_user_ids_string(), undefined);

    set_filter_result(["bob@zulip.com,alice@zulip.com"]);
    assert.equal(pm_list.get_active_user_ids_string(), "101,102");
});

function private_filter() {
    return {
        operands: (operand) => {
            assert.equal(operand, "is");
            return ["private", "starred"];
        },
    };
}

test("is_all_privates", ({override}) => {
    let filter;
    override(narrow_state, "filter", () => filter);

    filter = undefined;
    assert.equal(pm_list.is_all_privates(), false);

    filter = private_filter();
    assert.equal(pm_list.is_all_privates(), true);
});

test("expand", ({override, override_rewire}) => {
    override(narrow_state, "filter", private_filter);
    override(narrow_state, "active", () => true);
    override_rewire(pm_list, "_build_private_messages_list", () => "PM_LIST_CONTENTS");
    let html_updated;
    override(vdom, "update", () => {
        html_updated = true;
    });

    assert.ok(!$(".top_left_private_messages").hasClass("active-filter"));

    pm_list.expand();
    assert.ok(html_updated);
    assert.ok($(".top_left_private_messages").hasClass("active-filter"));
});

test("update_private_messages", ({override, override_rewire}) => {
    let html_updated;
    let container_found;

    override(narrow_state, "filter", private_filter);
    override(narrow_state, "active", () => true);
    override_rewire(pm_list, "_build_private_messages_list", () => "PM_LIST_CONTENTS");

    $("#private-container").find = (sel) => {
        assert.equal(sel, "ul");
        container_found = true;
    };

    override(vdom, "update", (replace_content, find) => {
        html_updated = true;

        // get line coverage for simple one-liners
        replace_content();
        find();
    });

    pm_list.expand();
    pm_list.update_private_messages();
    assert.ok(html_updated);
    assert.ok(container_found);
});

test("ensure coverage", ({override}) => {
    // These aren't rigorous; they just cover cases
    // where functions early exit.
    override(narrow_state, "active", () => false);

    with_field(
        vdom,
        "update",
        () => {
            throw new Error("we should not update the dom");
        },
        () => {
            pm_list.update_private_messages();
        },
    );
});
