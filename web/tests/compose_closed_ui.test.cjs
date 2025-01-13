"use strict";

// Setup
const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

// Mocking and stubbing things
set_global("document", "document-stub");
const message_lists = mock_esm("../src/message_lists");
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
mock_esm("../src/people.ts", {
    maybe_get_user_by_id: noop,
});

const stream_data = zrequire("stream_data");
// Code we're actually using/testing
const compose_closed_ui = zrequire("compose_closed_ui");
const {Filter} = zrequire("filter");
const {MessageList} = zrequire("message_list");
const {MessageListData} = zrequire("message_list_data");
const {set_realm} = zrequire("state_data");

const REALM_EMPTY_TOPIC_DISPLAY_NAME = "general chat";
set_realm({realm_empty_topic_display_name: REALM_EMPTY_TOPIC_DISPLAY_NAME});

// Helper test function
function test_reply_label(expected_label) {
    const label = $("#left_bar_compose_reply_button_big").text();
    const prepend_text_length = "translated: Message ".length;
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
                stream_id: stream_one.stream_id,
                topic: "first_topic",
            },
            {
                id: 1,
                stream_id: stream_one.stream_id,
                topic: "second_topic",
            },
            {
                id: 2,
                stream_id: stream_two.stream_id,
                topic: "third_topic",
            },
            {
                id: 3,
                stream_id: stream_two.stream_id,
                topic: "second_topic",
            },
            {
                id: 4,
                display_reply_to: "some user",
            },
            {
                id: 5,
                display_reply_to: "some user, other user",
            },
            {
                id: 6,
                stream_id: stream_two.stream_id,
                topic: "",
            },
        ],
        {},
        true,
    );

    const expected_labels = [
        "#first_stream > first_topic",
        "#first_stream > second_topic",
        "#second_stream > third_topic",
        "#second_stream > second_topic",
        "some user",
        "some user, other user",
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
        `translated HTML: Message #second_stream > <span class="empty-topic-display">translated: ${REALM_EMPTY_TOPIC_DISPLAY_NAME}</span>`,
        label_html,
    );
});

run_test("test_custom_message_input", () => {
    const stream = {
        subscribed: true,
        name: "stream test",
        stream_id: 10,
    };
    stream_data.add_sub(stream);
    compose_closed_ui.update_reply_recipient_label({
        stream_id: stream.stream_id,
        topic: "topic test",
    });
    test_reply_label("#stream test > topic test");
});

run_test("empty_narrow", () => {
    message_lists.current.visibly_empty = () => true;
    compose_closed_ui.update_reply_recipient_label();
    const label = $("#left_bar_compose_reply_button_big").text();
    assert.equal(label, "translated: Compose message");
});
