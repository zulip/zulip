"use strict";

// Setup
const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// Mocking and stubbing things
set_global("document", "document-stub");
const message_lists = mock_esm("../src/message_lists");
const recent_view_util = mock_esm("../src/recent_view_util");
function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
        is_current_message_list: () => true,
    };
}
mock_esm("../src/message_list_view", {
    MessageListView,
});
mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});

const stream_data = zrequire("stream_data");
// Code we're actually using/testing
const compose_closed_ui = zrequire("compose_closed_ui");
const people = zrequire("people");
const {Filter} = zrequire("filter");
const {MessageList} = zrequire("message_list");
const {MessageListData} = zrequire("message_list_data");
const {set_current_user, set_realm} = zrequire("state_data");

const current_user = {
    email: "alice@zulip.com",
    user_id: 1,
    full_name: "Alice",
};
set_current_user(current_user);
people.add_active_user(current_user);
people.add_active_user({
    email: "bob@zulip.com",
    user_id: 2,
    full_name: "Bob",
});
people.add_active_user({
    email: "zoe@zulip.com",
    user_id: 3,
    full_name: "Zoe",
});
people.initialize_current_user(1);

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "general chat";
set_realm({realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME});

// Helper test function
function test_reply_label(expected_label) {
    const label = $("#left_bar_compose_reply_button_big").html();
    const prepend_text_length = "Message ".length;
    assert.equal(
        label.slice(prepend_text_length),
        expected_label,
        "'" + label.slice(prepend_text_length),
        Number("' did not match '") + expected_label + "'",
    );
}

run_test("reply_label", () => {
    // Mocking up a test message list
    const filter = new Filter([]);
    const list = new MessageList({
        data: new MessageListData({
            excludes_muted_topics: false,
            filter,
        }),
    });
    message_lists.current = list;
    const stream_one = {
        subscribed: true,
        name: "first_stream",
        stream_id: 1,
    };
    stream_data.add_sub(stream_one);
    const stream_two = {
        subscribed: true,
        name: "second_stream",
        stream_id: 2,
    };
    stream_data.add_sub(stream_two);
    list.add_messages(
        [
            {
                id: 0,
                is_stream: true,
                is_private: false,
                stream_id: stream_one.stream_id,
                topic: "first_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 1,
                is_stream: true,
                is_private: false,
                stream_id: stream_one.stream_id,
                topic: "second_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 2,
                is_stream: true,
                is_private: false,
                stream_id: stream_two.stream_id,
                topic: "third_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 3,
                is_stream: true,
                is_private: false,
                stream_id: stream_two.stream_id,
                topic: "second_topic",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 4,
                is_stream: false,
                is_private: true,
                to_user_ids: "2",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 5,
                is_stream: false,
                is_private: true,
                to_user_ids: "2,3",
                sent_by_me: false,
                sender_id: 2,
            },
            {
                id: 6,
                is_stream: true,
                is_private: false,
                stream_id: stream_two.stream_id,
                topic: "",
                sent_by_me: false,
                sender_id: 2,
            },
        ],
        {},
        true,
    );

    const expected_labels = [
        "#first_stream &gt; first_topic",
        "#first_stream &gt; second_topic",
        "#second_stream &gt; third_topic",
        "#second_stream &gt; second_topic",
        "Bob",
        "Bob, Zoe",
    ];

    // Initialize the code we're testing.
    compose_closed_ui.initialize();

    // Run the tests!
    let first = true;
    for (const expected_label of expected_labels) {
        if (first) {
            list.select_id(list.first().id);
            first = false;
        } else {
            list.select_id(list.next());
        }
        test_reply_label(expected_label);
    }

    // Separately test for empty string topic as the topic is specially decorated here.
    list.select_id(list.next());
    const label_html = $("#left_bar_compose_reply_button_big").html();
    assert.equal(
        `Message #second_stream &gt; <span class="empty-topic-display">translated: ${REALM_EMPTY_TOPIC_DISPLAY_NAME}</span>`,
        label_html,
    );
});

run_test("empty_narrow", () => {
    message_lists.current.visibly_empty = () => true;
    compose_closed_ui.update_recipient_text_for_reply_button();
    const label = $("#left_bar_compose_reply_button_big").text();
    assert.equal(label, "translated: Compose message");
});

run_test("test_non_message_list_input", () => {
    message_lists.current = undefined;
    recent_view_util.is_visible = () => true;
    const stream = {
        subscribed: true,
        name: "stream test",
        stream_id: 10,
    };
    stream_data.add_sub(stream);

    // Channel and topic row.
    compose_closed_ui.update_recipient_text_for_reply_button({
        stream_id: stream.stream_id,
        topic: "topic test",
    });
    test_reply_label("#stream test &gt; topic test");

    // Direct message conversation with current user row.
    compose_closed_ui.update_recipient_text_for_reply_button({
        user_ids: [current_user.user_id],
    });
    let label = $("#left_bar_compose_reply_button_big").html();
    assert.equal(label, "Message yourself");

    // Invalid data for a the reply button text.
    compose_closed_ui.update_recipient_text_for_reply_button({
        invalid_field: "something unexpected",
    });
    label = $("#left_bar_compose_reply_button_big").text();
    assert.equal(label, "translated: Compose message");
});
