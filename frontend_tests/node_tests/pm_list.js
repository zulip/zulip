"use strict";

const {strict: assert} = require("assert");

const rewiremock = require("rewiremock/node");

const {set_global, with_field, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

const narrow_state = set_global("narrow_state", {});
set_global("ui", {
    get_content_element: (element) => element,
});
set_global("stream_popover", {
    hide_topic_popover() {},
});
const unread = set_global("unread", {});
const unread_ui = {__esModule: true};
rewiremock("../../static/js/unread_ui").with(unread_ui);
const vdom = {
    __esModule: true,
    render: () => "fake-dom-for-pm-list",
};
rewiremock("../../static/js/vdom").with(vdom);
const pm_list_dom = set_global("pm_list_dom", {});

rewiremock.enable();

zrequire("presence");
zrequire("buddy_data");
zrequire("hash_util");
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

run_test("close", () => {
    let collapsed;
    $("#private-container").empty = () => {
        collapsed = true;
    };
    pm_list.close();
    assert(collapsed);
});

run_test("build_private_messages_list", (override) => {
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
            fraction_present: undefined,
            is_group: true,
        },
    ];

    assert.deepEqual(pm_data, expected_data);

    num_unread_for_person = 0;
    pm_list._build_private_messages_list();
    expected_data[0].unread = 0;
    expected_data[0].is_zero = true;
    assert.deepEqual(pm_data, expected_data);

    pm_list.initialize();
    pm_list._build_private_messages_list();
    assert.deepEqual(pm_data, expected_data);
});

run_test("build_private_messages_list_bot", (override) => {
    const timestamp = 0;
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
            fraction_present: undefined,
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
            fraction_present: undefined,
            is_group: true,
        },
    ];

    assert.deepEqual(pm_data, expected_data);
});

run_test("update_dom_with_unread_counts", (override) => {
    let counts;
    let toggle_button_set;
    let expected_unread_count;

    override(narrow_state, "active", () => true);

    override(unread_ui, "set_count_toggle_button", (elt, count) => {
        toggle_button_set = true;
        assert.equal(count, expected_unread_count);
    });

    const total_value = $.create("total-value-stub");
    const total_count = $.create("total-count-stub");
    const private_li = $(".top_left_private_messages");
    private_li.set_find_results(".count", total_count);
    total_count.set_find_results(".value", total_value);

    counts = {
        private_message_count: 10,
    };

    expected_unread_count = 10;

    toggle_button_set = false;
    pm_list.update_dom_with_unread_counts(counts);
    assert(toggle_button_set);

    counts = {
        private_message_count: 0,
    };

    expected_unread_count = 0;

    toggle_button_set = false;
    pm_list.update_dom_with_unread_counts(counts);
    assert(toggle_button_set);
});

run_test("get_active_user_ids_string", (override) => {
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

run_test("is_all_privates", (override) => {
    let filter;
    override(narrow_state, "filter", () => filter);

    filter = undefined;
    assert.equal(pm_list.is_all_privates(), false);

    filter = private_filter();
    assert.equal(pm_list.is_all_privates(), true);
});

run_test("expand", (override) => {
    override(narrow_state, "filter", private_filter);
    override(narrow_state, "active", () => true);
    override(pm_list, "_build_private_messages_list", () => "PM_LIST_CONTENTS");
    let html_updated;
    override(vdom, "update", () => {
        html_updated = true;
    });

    assert(!$(".top_left_private_messages").hasClass("active-filter"));

    pm_list.expand();
    assert(html_updated);
    assert($(".top_left_private_messages").hasClass("active-filter"));
});

run_test("update_private_messages", (override) => {
    let html_updated;
    let container_found;

    override(narrow_state, "active", () => true);
    override(pm_list, "_build_private_messages_list", () => "PM_LIST_CONTENTS");

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

    pm_list.update_private_messages();
    assert(html_updated);
    assert(container_found);
});

run_test("ensure coverage", (override) => {
    // These aren't rigorous; they just cover cases
    // where functions early exit.
    override(narrow_state, "active", () => false);

    with_field(
        pm_list,
        "rebuild_recent",
        () => {
            throw new Error("we should not call rebuild_recent");
        },
        () => {
            pm_list.update_private_messages();
        },
    );
});
rewiremock.disable();
