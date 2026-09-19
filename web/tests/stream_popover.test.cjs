"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {$} = require("./lib/zjquery.cjs");

const {Filter} = zrequire("filter");
const inbox_util = zrequire("inbox_util");
const {MessageList} = zrequire("message_list");
const {MessageListData} = zrequire("message_list_data");
const message_lists = zrequire("message_lists");
const message_util = zrequire("message_util");
const people = zrequire("people");
const {recent_view_messages_data} = zrequire("recent_view_messages_data");
const stream_data = zrequire("stream_data");
const stream_popover = zrequire("stream_popover");
const user_topics = zrequire("user_topics");

const rome = {name: "Rome", stream_id: 1001, subscribed: true};
stream_data.add_sub_for_tests(rome);

// Adding messages to a message list records their senders as
// participants of the conversation, so the sender has to be a user we
// know about.
const sender = make_user();
people.add_active_user(sender);

function make_channel_message(id, topic) {
    return {id, type: "stream", stream_id: rome.stream_id, topic, sender_id: sender.user_id};
}

const foo_messages = [
    make_channel_message(101, "foo"),
    make_channel_message(102, "foo"),
    make_channel_message(103, "foo"),
];
const selected_message_id = 102;

// Recent conversations caches the newest slice of the user's history.
// Here that window starts at the topic's last message: the two older
// ones were sent long enough ago to have fallen out of it, which is
// the situation the count was reported wrong in.
recent_view_messages_data.add_messages(
    [foo_messages.at(-1), make_channel_message(104, "boo"), make_channel_message(105, "boo")],
    true,
);

function set_current_view(filter_terms, messages, fetch_state = {}) {
    const {found_oldest = true, found_newest = true, history_limited = false} = fetch_state;
    const filter = new Filter(filter_terms);
    const message_list = new MessageList({
        data: new MessageListData({
            filter,
            excludes_muted_topics: filter.excludes_muted_topics(),
            excludes_muted_users: filter.excludes_muted_users(),
        }),
        is_node_test: true,
    });
    message_list.data.add_messages(messages, true);
    message_list.data.fetch_status.finish_older_batch({
        update_loading_indicator: false,
        found_oldest,
        history_limited,
    });
    message_list.data.fetch_status.finish_newer_batch([], {
        update_loading_indicator: false,
        found_newest,
    });

    inbox_util.set_visible(false);
    message_lists.set_current(message_list);
    return message_list;
}

function set_current_channel_topics_view(stream_id) {
    // The list of topics in a channel, like the inbox it is rendered
    // with, has no message list of its own.
    message_lists.set_current(undefined);
    inbox_util.set_filter(new Filter([{operator: "channel", operand: stream_id.toString()}]));
    inbox_util.set_visible(true);
}

function topic_view_terms(topic_name) {
    return [
        {operator: "channel", operand: rome.stream_id.toString()},
        {operator: "topic", operand: topic_name},
    ];
}

function count_of_messages_to_be_moved(selected_option, topic_name, message_id) {
    return stream_popover.get_move_messages_count(
        selected_option,
        rome.stream_id,
        topic_name,
        message_id,
    ).count;
}

function count_text(selected_option, topic_name, message_id) {
    stream_popover.update_move_messages_count_text(
        selected_option,
        rome.stream_id,
        topic_name,
        message_id,
    );
    return $("#move_messages_count").text();
}

run_test("count of messages to be moved", () => {
    const message_list = set_current_view(topic_view_terms("foo"), foo_messages);

    // The view we are in has the whole topic loaded; recent
    // conversations has only its newest message.
    assert.equal(message_list.all_messages().length, 3);
    assert.equal(message_util.get_loaded_messages_in_topic(rome.stream_id, "foo").length, 1);

    assert.equal(count_of_messages_to_be_moved("change_one", "foo", selected_message_id), 1);

    // The count comes from the view, so it sees the whole topic: two of
    // its messages are at or after the selected one.
    assert.equal(count_of_messages_to_be_moved("change_later", "foo", selected_message_id), 2);
    assert.equal(count_of_messages_to_be_moved("change_all", "foo"), 3);
});

run_test("count text in a conversation view", () => {
    set_current_view(topic_view_terms("foo"), foo_messages);

    assert.equal(
        count_text("change_one", "foo", selected_message_id),
        "translated: 1 message will be moved.",
    );

    // This view is narrowed to the topic and has fetched all of it, so
    // the count is exact.
    assert.equal(
        count_text("change_later", "foo", selected_message_id),
        "translated: 2 messages will be moved.",
    );
    assert.equal(count_text("change_all", "foo"), "translated: 3 messages will be moved.");

    // A view that has not fetched the whole topic can only give a
    // lower bound.
    set_current_view(topic_view_terms("foo"), foo_messages, {found_oldest: false});
    assert.equal(count_text("change_all", "foo"), "translated: 3+ messages will be moved.");

    // A `near` term points at one message of the conversation without
    // narrowing the view any further, so the count stays exact.
    set_current_view(
        [...topic_view_terms("foo"), {operator: "near", operand: selected_message_id.toString()}],
        foo_messages,
    );
    assert.equal(count_text("change_all", "foo"), "translated: 3 messages will be moved.");
});

run_test("count text in a channel view", () => {
    const channel_view_terms = [{operator: "channel", operand: rome.stream_id.toString()}];
    set_current_view(channel_view_terms, foo_messages);
    assert.equal(count_text("change_all", "foo"), "translated: 3 messages will be moved.");

    // A `near` term points at one message without narrowing the
    // view, so a channel view that has one still contains the whole
    // topic.
    set_current_view(
        [...channel_view_terms, {operator: "near", operand: selected_message_id.toString()}],
        foo_messages,
    );
    assert.equal(count_text("change_all", "foo"), "translated: 3 messages will be moved.");

    // Muting a topic hides its messages from a channel view, but a move
    // still moves them, so the count should not change.
    user_topics.update_user_topics(
        rome.stream_id,
        rome.name,
        "foo",
        user_topics.all_visibility_policies.MUTED,
        0,
    );
    const message_list = set_current_view(channel_view_terms, foo_messages);
    assert.deepEqual(message_list.all_messages(), []);
    assert.equal(count_text("change_all", "foo"), "translated: 3 messages will be moved.");

    user_topics.update_user_topics(
        rome.stream_id,
        rome.name,
        "foo",
        user_topics.all_visibility_policies.INHERIT,
        0,
    );
});

run_test("count text in views that cannot answer for the topic", () => {
    // An interleaved view can hold messages of the topic without
    // holding all of them, and cannot tell us which of those it is, so
    // we count from the recent conversations cache and say the count is
    // a lower bound.
    set_current_view([], foo_messages);
    assert.equal(count_text("change_all", "foo"), "translated: 1+ messages will be moved.");

    set_current_channel_topics_view(rome.stream_id);
    assert.equal(count_text("change_all", "foo"), "translated: 1+ messages will be moved.");
});

run_test("count text when the channel's history is limited", () => {
    // The user cannot see the messages older than the ones the server
    // sent us, but moving the topic moves those too.
    set_current_view(topic_view_terms("foo"), foo_messages, {history_limited: true});
    assert.equal(count_text("change_all", "foo"), "translated: 3+ messages will be moved.");

    // The messages we cannot see are all older than the selected one,
    // so this count is still exact.
    assert.equal(
        count_text("change_later", "foo", selected_message_id),
        "translated: 2 messages will be moved.",
    );
});
