"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params} = require("./lib/zpage_params");

const {Filter} = zrequire("filter");
const {MessageList} = zrequire("message_list");
const message_lists = zrequire("message_lists");
const popover_menus_data = zrequire("popover_menus_data");
const people = zrequire("people");
const compose = zrequire("compose");
const reactions = mock_esm("../src/reactions");

const noop = function () {};

// Define MessageList stuff
function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
        clear_rendering_state: noop,
        message_containers: new Map(),
    };
}
mock_esm("../src/message_list_view", {
    MessageListView,
});

// Define test users
const member_user = {
    user_id: 1000,
    full_name: "Test member_user",
    email: "member_user@example.com",
    is_admin: false,
    is_guest: false,
    is_member: true,
};

const admin_user = {
    user_id: 2000,
    full_name: "Test admin_user",
    email: "admin_user@example.com",
    is_admin: true,
    is_guest: false,
};

const guest_user = {
    user_id: 3000,
    full_name: "Test guest_user",
    email: "guest_user@example.com",
    is_admin: false,
    is_guest: true,
};

const moderator_user = {
    user_id: 2000,
    full_name: "Test moderator_user",
    email: "moderator_user@example.com",
    is_admin: false,
    is_guest: false,
    is_moderator: true,
};

const me = {
    user_id: 999,
    full_name: "Test Myself",
    email: "me@example.com",
    is_admin: false,
    is_guest: false,
};

// Helper functions:
function add_initialize_users() {
    // Initialize people
    people.init();

    // Add users
    people.add_active_user(member_user);
    people.add_active_user(admin_user);
    people.add_active_user(guest_user);
    people.add_active_user(me);

    // Initialize current user
    people.initialize_current_user(me.user_id);
}

function init_message_list() {
    // Initialize message list
    const filter = new Filter();
    const list = new MessageList({
        filter,
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
function set_page_params_no_edit_restrictions() {
    page_params.is_spectator = false;
    page_params.realm_allow_message_editing = true;
    page_params.realm_message_content_edit_limit_seconds = null;
    page_params.realm_allow_edit_history = true;
    page_params.realm_message_content_delete_limit_seconds = null;
    page_params.realm_delete_own_message_policy = 1;
    page_params.realm_enable_read_receipts = true;
    page_params.realm_edit_topic_policy = 5;
}

// reset the user status
function reset_page_params_user_status() {
    page_params.is_admin = false;
    page_params.is_member = false;
    page_params.is_moderator = false;
    page_params.is_spectator = false;
    page_params.is_guest = false;
}

// Test init function
function test(label, f) {
    run_test(label, (helpers) => {
        // Clear stuff for testing environment
        add_initialize_users();
        message_lists.initialize();
        f(helpers);
    });
}

const messages = [
    {
        id: 1,
        sender_id: me.user_id,
        is_hidden: false,
        sent_by_me: true,
        locally_echoed: false,
        is_stream: true,
        stream_id: 1,
        unread: false,
        collapsed: false,
        clean_reaction: new Map(),
        topic: compose.empty_topic_placeholder(),
        edit_history: [
            {
                prev_content: "Previous content",
                prev_stream: 0,
                prev_topic: "Previous topic",
            },
        ],
    },
    {
        id: 2,
        sender_id: admin_user.user_id,
        is_hidden: false,
        sent_by_me: true,
        locally_echoed: false,
        is_stream: true,
        stream_id: 1,
        unread: false,
        collapsed: false,
        clean_reaction: new Map(),
        topic: compose.empty_topic_placeholder(),
        edit_history: [
            {
                prev_content: "Previous content",
                prev_stream: 0,
                prev_topic: "Previous topic",
            },
        ],
    },
    {
        id: 3,
        sender_id: guest_user.user_id,
        is_hidden: false,
        sent_by_me: true,
        locally_echoed: false,
        is_stream: true,
        stream_id: 1,
        unread: false,
        collapsed: false,
        clean_reaction: new Map(),
        topic: compose.empty_topic_placeholder(),
        edit_history: [
            {
                prev_content: "Previous content",
                prev_stream: 0,
                prev_topic: "Previous topic",
            },
        ],
    },
    {
        id: 5,
        sender_id: moderator_user.user_id,
        is_hidden: false,
        sent_by_me: true,
        locally_echoed: false,
        is_stream: true,
        stream_id: 1,
        unread: false,
        collapsed: false,
        clean_reaction: new Map(),
        topic: compose.empty_topic_placeholder(),
        edit_history: [
            {
                prev_content: "Previous content",
                prev_stream: 0,
                prev_topic: "Previous topic",
            },
        ],
    },
    {
        id: 6,
        sender_id: member_user.user_id,
        is_hidden: false,
        sent_by_me: true,
        locally_echoed: false,
        is_stream: true,
        stream_id: 1,
        unread: false,
        collapsed: false,
        clean_reaction: new Map(),
        topic: compose.empty_topic_placeholder(),
        edit_history: [
            {
                prev_content: "Previous content",
                prev_stream: 0,
                prev_topic: "Previous topic",
            },
        ],
    },
];

// Test functions
test("my_message_all_actions", ({override}) => {
    // Set page parameters.
    set_page_params_no_edit_restrictions();
    reset_page_params_user_status();

    // Get message with maximum permissions available
    // Initialize message list
    const list = init_message_list();
    message_lists.set_current(list);
    override(reactions, "message_has_reactions", noop);
    add_message_with_view(list, messages);
    reset_page_params_user_status();
    page_params.is_member = true;

    let response = popover_menus_data.get_actions_popover_content_context(1);
    assert.deepEqual(response, {
        message_id: 1,
        stream_id: 1,
        editability_menu_item: "translated: Edit message",
        move_message_menu_item: undefined,
        should_display_mark_as_unread: true,
        view_source_menu_item: undefined,
        should_display_collapse: true,
        should_display_uncollapse: false,
        should_display_add_reaction_option: undefined,
        should_display_edit_history_option: true,
        should_display_hide_option: false,
        conversation_time_uri: "http://zulip.zulipdev.com/undefined/near/1",
        narrowed: false,
        should_display_delete_option: true,
        should_display_read_receipts_option: true,
        should_display_reminder_option: false,
        should_display_quote_and_reply: true,
    });

    reset_page_params_user_status();
    page_params.is_guest = true;
    response = popover_menus_data.get_actions_popover_content_context(3);
    assert.deepEqual(response, {
        message_id: 3,
        stream_id: 1,
        editability_menu_item: "translated: Edit message",
        move_message_menu_item: undefined,
        should_display_mark_as_unread: true,
        view_source_menu_item: undefined,
        should_display_collapse: true,
        should_display_uncollapse: false,
        should_display_add_reaction_option: undefined,
        should_display_edit_history_option: true,
        should_display_hide_option: false,
        conversation_time_uri: "http://zulip.zulipdev.com/undefined/near/3",
        narrowed: false,
        should_display_delete_option: false,
        should_display_read_receipts_option: true,
        should_display_reminder_option: false,
        should_display_quote_and_reply: true,
    });

    reset_page_params_user_status();
    page_params.is_spectator = true;
    response = popover_menus_data.get_actions_popover_content_context(6);
    assert.deepEqual(response, {
        message_id: 6,
        stream_id: 1,
        editability_menu_item: "translated: Edit message",
        move_message_menu_item: undefined,
        should_display_mark_as_unread: false,
        view_source_menu_item: undefined,
        should_display_collapse: false,
        should_display_uncollapse: false,
        should_display_add_reaction_option: undefined,
        should_display_edit_history_option: false,
        should_display_hide_option: false,
        conversation_time_uri: "http://zulip.zulipdev.com/undefined/near/6",
        narrowed: false,
        should_display_delete_option: false,
        should_display_read_receipts_option: false,
        should_display_reminder_option: false,
        should_display_quote_and_reply: false,
    });

    reset_page_params_user_status();
    page_params.is_moderator = true;
    response = popover_menus_data.get_actions_popover_content_context(5);
    assert.deepEqual(response, {
        message_id: 5,
        stream_id: 1,
        editability_menu_item: "translated: Edit message",
        move_message_menu_item: undefined,
        should_display_mark_as_unread: true,
        view_source_menu_item: undefined,
        should_display_collapse: true,
        should_display_uncollapse: false,
        should_display_add_reaction_option: undefined,
        should_display_edit_history_option: true,
        should_display_hide_option: false,
        conversation_time_uri: "http://zulip.zulipdev.com/undefined/near/5",
        narrowed: false,
        should_display_delete_option: true,
        should_display_read_receipts_option: true,
        should_display_reminder_option: false,
        should_display_quote_and_reply: true,
    });

    reset_page_params_user_status();
    page_params.is_admin = true;
    response = popover_menus_data.get_actions_popover_content_context(2);
    assert.deepEqual(response, {
        message_id: 2,
        stream_id: 1,
        editability_menu_item: "translated: Edit message",
        move_message_menu_item: undefined,
        should_display_mark_as_unread: true,
        view_source_menu_item: undefined,
        should_display_collapse: true,
        should_display_uncollapse: false,
        should_display_add_reaction_option: undefined,
        should_display_edit_history_option: true,
        should_display_hide_option: false,
        conversation_time_uri: "http://zulip.zulipdev.com/undefined/near/2",
        narrowed: false,
        should_display_delete_option: true,
        should_display_read_receipts_option: true,
        should_display_reminder_option: false,
        should_display_quote_and_reply: true,
    });
});

test("not_my_message_view", ({override}) => {
    set_page_params_no_edit_restrictions();
    reset_page_params_user_status();

    // Get message that is movable with viewable source
    const list = init_message_list();
    message_lists.set_current(list);
    override(reactions, "message_has_reactions", noop);
    // Verify context for actions popover rendering for a message sent by
    // another user that the current user has permission to move.
    const messages = [
        {
            id: 1,
            sender_id: member_user.user_id,
            is_hidden: false,
            sent_by_me: false,
            locally_echoed: false,
            is_stream: true,
            stream_id: 1,
            type: "stream",
            unread: false,
            collapsed: false,
            clean_reactions: new Map(),
            topic: compose.empty_topic_placeholder(),
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
    assert.deepEqual(response, {
        message_id: 1,
        stream_id: 1,
        editability_menu_item: undefined,
        move_message_menu_item: "translated: Move messages",
        should_display_mark_as_unread: false,
        view_source_menu_item: "translated: View message source",
        should_display_collapse: true,
        should_display_uncollapse: false,
        should_display_add_reaction_option: undefined,
        should_display_edit_history_option: true,
        should_display_hide_option: false,
        conversation_time_uri:
            "http://zulip.zulipdev.com/#narrow/stream/1-unknown/topic/translated.3A.20.28no.20topic.29/near/1",
        narrowed: false,
        should_display_delete_option: false,
        should_display_read_receipts_option: true,
        should_display_reminder_option: false,
        should_display_quote_and_reply: true,
    });
});
