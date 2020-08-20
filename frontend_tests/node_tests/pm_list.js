"use strict";

set_global("$", global.make_zjquery());

set_global("narrow_state", {});
set_global("ui", {
    get_content_element: (element) => element,
});
set_global("stream_popover", {
    hide_topic_popover() {},
});
set_global("unread", {});
set_global("unread_ui", {});
set_global("vdom", {
    render: () => "fake-dom-for-pm-list",
});
set_global("pm_list_dom", {});

zrequire("user_status");
zrequire("presence");
zrequire("buddy_data");
zrequire("hash_util");
const people = zrequire("people");
const pm_conversations = zrequire("pm_conversations");
zrequire("pm_list");

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
    $("#private-container").empty = function () {
        collapsed = true;
    };
    pm_list.close();
    assert(collapsed);
});

run_test("build_private_messages_list", () => {
    const timestamp = 0;
    pm_conversations.recent.insert([101, 102], timestamp);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    let pm_data;

    pm_list_dom.pm_ul = (data) => {
        pm_data = data;
    };

    narrow_state.filter = () => {};
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

    global.unread.num_unread_for_person = function () {
        return 0;
    };
    pm_list._build_private_messages_list();
    expected_data[0].unread = 0;
    expected_data[0].is_zero = true;
    assert.deepEqual(pm_data, expected_data);

    pm_list.initialize();
    pm_list._build_private_messages_list();
    assert.deepEqual(pm_data, expected_data);
});

run_test("build_private_messages_list_bot", () => {
    const timestamp = 0;
    pm_conversations.recent.insert([314], timestamp);

    global.unread.num_unread_for_person = function () {
        return 1;
    };

    let pm_data;
    pm_list_dom.pm_ul = (data) => {
        pm_data = data;
    };

    narrow_state.active = () => true;

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

run_test("update_dom_with_unread_counts", () => {
    let counts;
    let toggle_button_set;

    const total_value = $.create("total-value-stub");
    const total_count = $.create("total-count-stub");
    const private_li = $(".top_left_private_messages");
    private_li.set_find_results(".count", total_count);
    total_count.set_find_results(".value", total_value);

    counts = {
        private_message_count: 10,
    };

    unread_ui.set_count_toggle_button = function (elt, count) {
        toggle_button_set = true;
        assert.equal(count, 10);
    };

    toggle_button_set = false;
    pm_list.update_dom_with_unread_counts(counts);
    assert(toggle_button_set);

    counts = {
        private_message_count: 0,
    };

    unread_ui.set_count_toggle_button = function (elt, count) {
        toggle_button_set = true;
        assert.equal(count, 0);
    };

    toggle_button_set = false;
    pm_list.update_dom_with_unread_counts(counts);
    assert(toggle_button_set);
});

run_test("get_active_user_ids_string", () => {
    narrow_state.filter = () => {};

    assert.equal(pm_list.get_active_user_ids_string(), undefined);

    function set_filter_result(emails) {
        narrow_state.filter = () => ({
            operands: (operand) => {
                assert.equal(operand, "pm-with");
                return emails;
            },
        });
    }

    set_filter_result([]);
    assert.equal(pm_list.get_active_user_ids_string(), undefined);

    set_filter_result(["bob@zulip.com,alice@zulip.com"]);
    assert.equal(pm_list.get_active_user_ids_string(), "101,102");
});

run_test("is_all_privates", () => {
    narrow_state.filter = () => {};

    assert.equal(pm_list.is_all_privates(), false);

    narrow_state.filter = () => ({
        operands: (operand) => {
            assert.equal(operand, "is");
            return ["private", "starred"];
        },
    });

    assert.equal(pm_list.is_all_privates(), true);
});

function with_fake_list(f) {
    with_field(pm_list, "_build_private_messages_list", () => "PM_LIST_CONTENTS", f);
}

run_test("expand", () => {
    with_fake_list(() => {
        let html_updated;

        vdom.update = () => {
            html_updated = true;
        };

        pm_list.expand();

        assert(html_updated);
    });
});

run_test("update_private_messages", () => {
    narrow_state.active = () => true;

    $("#private-container").find = (sel) => {
        assert.equal(sel, "ul");
    };

    with_fake_list(() => {
        let html_updated;

        vdom.update = (replace_content, find) => {
            html_updated = true;

            // get line coverage for simple one-liners
            replace_content();
            find();
        };

        with_field(
            pm_list,
            "is_all_privates",
            () => true,
            () => {
                pm_list.update_private_messages();
            },
        );

        assert(html_updated);
        assert($(".top_left_private_messages").hasClass("active-filter"));
    });
});

run_test("ensure coverage", () => {
    // These aren't rigorous; they just cover cases
    // where functions early exit.
    narrow_state.active = () => false;
    pm_list.rebuild_recent = () => {
        throw Error("we should not call rebuild_recent");
    };
    pm_list.update_private_messages();
});
