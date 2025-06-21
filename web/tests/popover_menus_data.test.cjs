"use strict";

const assert = require("node:assert/strict");

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
    is_stream_archived: () => false,
    get_sub_by_id: () => noop,
    user_can_move_messages_within_channel: () => true,
});
mock_esm("../src/group_permission_settings", {
    get_group_permission_setting_config() {
        return {
            allow_everyone_group: false,
        };
    },
});

const current_user = {};
set_current_user(current_user);
const realm = {};
set_realm(realm);

// Define test users
const mike = {
    user_id: 1000,
    full_name: "Test Mike",
    email: "mike@example.com",
    is_admin: false,
    is_guest: false,
};

const bob = {
    user_id: 2000,
    full_name: "Test Bob",
    email: "bob@example.com",
    is_admin: false,
    is_guest: false,
};

const me = {
    user_id: 999,
    full_name: "Test Myself",
    email: "me@example.com",
    is_admin: false,
    is_guest: false,
};

const everyone = {
    name: "role:everyone",
    id: 2,
    members: new Set([999, 1000, 2000]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};
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
        $("<div>").width = noop;
        $("<div>").remove = noop;

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
    assert.equal(response.should_display_hide_option, false);
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
