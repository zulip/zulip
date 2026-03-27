"use strict";

const assert = require("node:assert/strict");

const {make_user_group} = require("./lib/example_group.cjs");
const {make_realm} = require("./lib/example_realm.cjs");
const {make_user} = require("./lib/example_user.cts");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const {Filter} = zrequire("filter");
const {MessageList} = zrequire("message_list");
const message_lists = zrequire("message_lists");

const popover_menus_data = zrequire("popover_menus_data");
const people = zrequire("people");
const user_groups = zrequire("user_groups");
const {MessageListData} = zrequire("message_list_data");
const {set_current_user, set_realm} = zrequire("state_data");
const settings_config = zrequire("settings_config");

const noop = function () {};

// Define MessageList stuff
function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
        clear_rendering_state: noop,
        get_row: () => ({
            find(selector) {
                assert.equal(selector, ".message_controls .reaction_button");
                return {
                    length: 1,
                    css(property) {
                        assert.equal(property, "display");
                        return "none";
                    },
                };
            },
        }),
        message_containers: new Map(),
    };
}
mock_esm("../src/message_list_view", {
    MessageListView,
});
mock_esm("../src/ui_util", {
    listener_for_preferred_color_scheme_change: noop,
});
mock_esm("../src/hash_util", {
    by_conversation_and_time_url: () => "conversation_and_time_url",
});
mock_esm("../src/stream_data", {
    is_subscribed: () => true,
    is_stream_archived_by_id: () => false,
    get_sub_by_id: () => noop,
    user_can_move_messages_within_channel: () => true,
    is_empty_topic_only_channel: () => false,
});
mock_esm("../src/group_permission_settings", {
    get_group_permission_setting_config() {
        return {
            allow_everyone_group: false,
        };
    },
});
mock_esm("../src/timerender", {
    display_time_zone: "UTC",
    get_localized_date_or_time_for_format(date) {
        // Return a simple date string for testing.
        const d = new Date(date);
        const months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ];
        return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
    },
});

const current_user = {};
set_current_user(current_user);
const realm = make_realm();
set_realm(realm);

// Define test users
const mike = make_user({
    user_id: 1000,
    full_name: "Test Mike",
    email: "mike@example.com",
});

const bob = make_user({
    user_id: 2000,
    full_name: "Test Bob",
    email: "bob@example.com",
});

const me = make_user({
    user_id: 999,
    full_name: "Test Myself",
    email: "me@example.com",
});

const everyone = make_user_group({
    name: "role:everyone",
    id: 2,
    members: new Set([999, 1000, 2000]),
    is_system_group: true,
    direct_subgroup_ids: new Set(),
});
user_groups.initialize({realm_user_groups: [everyone]});

// Helper functions:
function add_initialize_users() {
    // Initialize people
    people.init();

    // Add users
    people.add_active_user(mike);
    people.add_active_user(bob);
    people.add_active_user(me);

    // Initialize current user
    people.initialize_current_user(me.user_id);
}

function init_message_list() {
    const filter = new Filter([]);
    const list = new MessageList({
        data: new MessageListData({
            excludes_muted_topics: false,
            filter,
        }),
    });

    assert.equal(list.empty(), true);

    return list;
}

// Append message to message_list, also add container to message_lists
function add_message_with_view(list, messages) {
    list.append(messages, true);
    for (const message of messages) {
        message_lists.current.view.message_containers.set(message.id, {
            is_hidden: message.is_hidden,
        });
    }
}

// Function sets page parameters with no time constraints on editing the message.
// User is assumed to not be an admin.
function set_page_params_no_edit_restrictions({override}) {
    page_params.is_spectator = false;
    override(realm, "realm_allow_message_editing", true);
    override(realm, "realm_message_content_edit_limit_seconds", null);
    override(
        realm,
        "realm_message_edit_history_visibility_policy",
        settings_config.message_edit_history_visibility_policy_values.always.code,
    );
    override(realm, "realm_message_content_delete_limit_seconds", null);
    override(realm, "realm_enable_read_receipts", true);
    override(realm, "realm_move_messages_within_stream_limit_seconds", null);
}

// Test init function
function test(label, f) {
    run_test(label, (helpers) => {
        // Stubs for calculate_timestamp_widths()
        $("<div>")[0].remove = noop;

        // Clear stuff for testing environment
        add_initialize_users();
        message_lists.initialize();
        f(helpers);
    });
}

// Test functions
test("my_message_all_actions", ({override}) => {
    // Set page parameters.
    set_page_params_no_edit_restrictions({override});
    override(realm, "realm_can_delete_any_message_group", everyone.id);
    override(realm, "realm_can_delete_own_message_group", everyone.id);
    override(realm, "realm_can_move_messages_between_topics_group", everyone.id);
    override(current_user, "user_id", me.user_id);
    // Get message with maximum permissions available
    // Initialize message list
    const list = init_message_list();
    message_lists.set_current(list);

    // Assume message has been previously edited.
    // Message is sent by me, and is a stream. I should have all permissions to this message.
    const messages = [
        {
            id: 1,
            type: "stream",
            sender_id: me.user_id,
            is_hidden: false,
            sent_by_me: true,
            locally_echoed: false,
            is_stream: true,
            stream_id: 1,
            unread: false,
            collapsed: false,
            not_spectator: true,
            submessages: [],
            edit_history: [
                {
                    prev_content: "Previous content",
                    prev_stream: 0,
                    prev_topic: "Previous topic",
                },
            ],
        },
    ];

    add_message_with_view(list, messages);
    const response = popover_menus_data.get_actions_popover_content_context(1);
    assert.equal(response.message_id, 1);
    assert.equal(response.stream_id, 1);
    assert.equal(response.editability_menu_item, "translated: Edit message");
    assert.equal(response.move_message_menu_item, "translated: Move messages");
    assert.equal(response.should_display_mark_as_unread, true);
    assert.equal(response.view_source_menu_item, undefined);
    assert.equal(response.should_display_collapse, true);
    assert.equal(response.should_display_uncollapse, false);
    assert.equal(response.should_display_add_reaction_option, true);
    assert.equal(response.conversation_time_url, "conversation_and_time_url");
    assert.equal(response.should_display_delete_option, true);
    assert.equal(response.should_display_read_receipts_option, true);
    assert.equal(response.should_display_quote_message, true);
});

test("not_my_message_view_actions", ({override}) => {
    set_page_params_no_edit_restrictions({override});
    // Get message that is only viewable
    override(realm, "realm_can_delete_any_message_group", everyone.id);
    const list = init_message_list();
    message_lists.set_current(list);

    // Message is sent by somebody else and is a stream with previous history.
    // I should only be able to view this message with no edit/move permissions.
    const messages = [
        {
            id: 1,
            sender_id: mike.user_id,
            is_hidden: false,
            sent_by_me: false,
            locally_echoed: false,
            is_stream: true,
            stream_id: 1,
            collapsed: false,
            unread: false,
            edit_history: [
                {
                    prev_content: "Previous content",
                    prev_stream: 0,
                    prev_topic: "Previous topic",
                },
            ],
        },
    ];

    add_message_with_view(list, messages);

    const response = popover_menus_data.get_actions_popover_content_context(1);

    assert.equal(response.view_source_menu_item, "translated: View original message");
    assert.equal(response.editability_menu_item, undefined);
    assert.equal(response.move_message_menu_item, undefined);
});

test("not_my_message_view_source_and_move", ({override}) => {
    set_page_params_no_edit_restrictions({override});
    override(realm, "realm_can_delete_any_message_group", everyone.id);
    override(realm, "realm_can_move_messages_between_topics_group", everyone.id);
    override(current_user, "user_id", me.user_id);
    // Get message that is movable with viewable source

    const list = init_message_list();
    message_lists.set_current(list);

    // Message tests edge case where message it sent by someone else.
    // Message is movable, however--I should have only view permissions with the exception of moving the message.
    const messages = [
        {
            id: 1,
            sender_id: mike.user_id,
            is_hidden: false,
            sent_by_me: false,
            locally_echoed: false,
            is_stream: true,
            stream_id: 1,
            type: "stream",
            unread: false,
            collapsed: false,
            topic: "New topic",
            edit_history: [
                {
                    prev_content: "Previous content",
                    prev_stream: 0,
                    prev_topic: "Previous topic",
                },
            ],
        },
    ];

    add_message_with_view(list, messages);

    const response = popover_menus_data.get_actions_popover_content_context(1);
    assert.equal(response.view_source_menu_item, "translated: View original message");
    assert.equal(response.editability_menu_item, undefined);
    assert.equal(response.move_message_menu_item, "translated: Move messages");
});

// Helper to create a minimal message object with a given timestamp.
function make_message(id, timestamp) {
    return {id, timestamp};
}

function date_timestamp(date_string) {
    return new Date(date_string + "T12:00:00").getTime() / 1000;
}

run_test("get_scroll_to_date_suggestions - empty messages", () => {
    const result = popover_menus_data.get_scroll_to_date_suggestions([]);
    assert.deepEqual(result, []);
});

run_test("get_scroll_to_date_suggestions - all messages today", () => {
    const today = new Date();
    const today_ts = today.getTime() / 1000;
    const messages = [make_message(1, today_ts), make_message(2, today_ts + 60)];
    const result = popover_menus_data.get_scroll_to_date_suggestions(messages);
    assert.deepEqual(result, []);
});

run_test("get_scroll_to_date_suggestions - few unique dates", () => {
    // With 3 unique dates (all in the past), all should be suggested.
    const messages = [
        make_message(1, date_timestamp("2025-01-10")),
        make_message(2, date_timestamp("2025-01-10")),
        make_message(3, date_timestamp("2025-02-15")),
        make_message(4, date_timestamp("2025-03-20")),
    ];
    const result = popover_menus_data.get_scroll_to_date_suggestions(messages);
    assert.equal(result.length, 3);
    // Verify chronological order.
    assert.ok(result[0].iso_date_string < result[1].iso_date_string);
    assert.ok(result[1].iso_date_string < result[2].iso_date_string);
});

run_test("get_scroll_to_date_suggestions - many dates with gaps", () => {
    // Simulate a conversation with bursts separated by gaps.
    // Burst 1: Jan 5-7 (9 messages)
    // Gap: 20 days
    // Burst 2: Jan 27-28 (8 messages)
    // Gap: 15 days
    // Burst 3: Feb 12-14 (10 messages)
    // Gap: 25 days
    // Burst 4: Mar 11-12 (8 messages)
    const messages = [];
    let id = 1;
    // 4 bursts of conversation separated by multi-week gaps.
    for (const [count, date] of [
        // Burst 1
        [3, "2025-01-05"],
        [3, "2025-01-06"],
        [3, "2025-01-07"],
        // Burst 2
        [4, "2025-01-27"],
        [4, "2025-01-28"],
        // Burst 3
        [4, "2025-02-12"],
        [3, "2025-02-13"],
        [3, "2025-02-14"],
        // Burst 4
        [4, "2025-03-11"],
        [4, "2025-03-12"],
    ]) {
        for (let i = 0; i < count; i += 1) {
            messages.push(make_message(id, date_timestamp(date)));
            id += 1;
        }
    }

    const result = popover_menus_data.get_scroll_to_date_suggestions(messages);
    // We have 10 unique dates across 4 bursts; expect 3-4 suggestions.
    assert.ok(result.length >= 3 && result.length <= 4);
    // Verify chronological order.
    for (let i = 1; i < result.length; i += 1) {
        assert.ok(result[i - 1].iso_date_string < result[i].iso_date_string);
    }
    // The algorithm should prefer dates at the start of bursts (after gaps).
    // Jan 27 has a 20-day gap before it, Feb 12 has a 15-day gap,
    // Mar 11 has a 25-day gap — these should appear as suggestions.
    const iso_dates = result.map((s) => s.iso_date_string.slice(0, 10));
    // Burst-start dates (Jan 27, Feb 12, Mar 11) should be well represented.
    const burst_starts = new Set(["2025-01-27", "2025-02-12", "2025-03-11"]);
    const burst_start_count = iso_dates.filter((d) => burst_starts.has(d)).length;
    assert.ok(burst_start_count >= 2, `Expected >=2 burst starts, got ${burst_start_count}`);
});

run_test("get_scroll_to_date_suggestions - single date in the past", () => {
    const messages = [
        make_message(1, date_timestamp("2025-06-15")),
        make_message(2, date_timestamp("2025-06-15")),
    ];
    const result = popover_menus_data.get_scroll_to_date_suggestions(messages);
    assert.equal(result.length, 1);
});
