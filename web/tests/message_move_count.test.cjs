"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {make_message_list} = require("./lib/message_list.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const message_store = zrequire("message_store");
const stream_popover = zrequire("stream_popover");
const message_lists = zrequire("message_lists");
const people = zrequire("people");
const stream_data = zrequire("stream_data");

const narrow_state = mock_esm("../src/narrow_state");

const alice = make_user({email: "alice@example.com", user_id: 1, full_name: "Alice"});
const bob = make_user({email: "bob@example.com", user_id: 2, full_name: "Bob"});
const carol = make_user({email: "carol@example.com", user_id: 3, full_name: "Carol"});

people.add_active_user(alice);
people.add_active_user(bob);
people.add_active_user(carol);

const rome_sub = {name: "Rome", subscribed: true, stream_id: 1001};
stream_data.add_sub_for_tests(rome_sub);

const messages = [
    {id: 101, stream_id: rome_sub.stream_id, topic: "foo", sender_id: 1, type: "stream"},
    {id: 102, stream_id: rome_sub.stream_id, topic: "foo", sender_id: 2, type: "stream"},
    {id: 103, stream_id: rome_sub.stream_id, topic: "foo", sender_id: 3, type: "stream"},
    {id: 104, stream_id: rome_sub.stream_id, topic: "boo", sender_id: 1, type: "stream"},
    {id: 105, stream_id: rome_sub.stream_id, topic: "boo", sender_id: 2, type: "stream"},
    {id: 106, stream_id: rome_sub.stream_id, topic: "boo", sender_id: 3, type: "stream"},
];

for (const message of messages) {
    message_store.update_message_cache({
        type: "server_message",
        message,
    });
}

run_test("test_get_count_of_messages_to_be_moved", () => {
    const selected_message_id = 102;

    const filter_terms = [
        {operator: "channel", operand: rome_sub.stream_id.toString()},
        {operator: "topic", operand: "foo"},
        {operator: "with", operand: selected_message_id.toString()},
    ];

    message_lists.set_current(make_message_list(filter_terms));
    message_lists.current.all_messages = () => messages;

    let count = stream_popover.get_count_of_messages_to_be_moved(
        "change_one",
        rome_sub.stream_id,
        "foo",
        selected_message_id,
    );
    assert.equal(count, 1);

    count = stream_popover.get_count_of_messages_to_be_moved(
        "change_later",
        rome_sub.stream_id,
        "foo",
        selected_message_id,
    );
    assert.equal(count, 2);

    count = stream_popover.get_count_of_messages_to_be_moved(
        "change_all",
        rome_sub.stream_id,
        "foo",
        selected_message_id,
    );
    assert.equal(count, 3);
});

run_test("test_update_move_messages_count", ({override}) => {
    const selected_message_id = 102;

    const filter_terms = [
        {operator: "channel", operand: rome_sub.stream_id.toString()},
        {operator: "topic", operand: "foo"},
        {operator: "with", operand: selected_message_id.toString()},
    ];
    message_lists.set_current(make_message_list(filter_terms));
    message_lists.current.all_messages = () => messages;

    // Case 1: selected_option === "change_one"
    stream_popover.update_move_messages_count_text(
        "change_one",
        rome_sub.stream_id,
        "foo",
        selected_message_id,
    );
    assert.equal($("#move_messages_count").text(), "translated: 1 message will be moved.");

    // Case 2: selected_option === "change_later"

    // This is the general case when we are in topic narrow.
    override(narrow_state, "narrowed_by_topic_reply", () => true);
    override(narrow_state, "narrowed_by_stream_reply", () => false);
    override(narrow_state, "stream_id", () => rome_sub.stream_id);
    override(narrow_state, "topic", () => "foo");

    message_lists.current.data.fetch_status.finish_newer_batch([], {
        update_loading_indicator: false,
        found_newest: true,
    });
    message_lists.current.data.fetch_status.finish_older_batch({
        update_loading_indicator: false,
        found_oldest: true,
        history_limited: false,
    });

    assert.ok(message_lists.current.data.fetch_status.has_found_newest());
    assert.ok(message_lists.current.data.fetch_status.has_found_oldest());

    stream_popover.update_move_messages_count_text(
        "change_later",
        rome_sub.stream_id,
        "foo",
        selected_message_id,
    );
    assert.equal($("#move_messages_count").text(), "translated: 2 messages will be moved.");

    // This is the case when we are in an interleaved view.
    override(narrow_state, "narrowed_by_topic_reply", () => false);
    override(narrow_state, "narrowed_by_stream_reply", () => false);
    override(narrow_state, "stream_id", () => rome_sub.stream_id);
    override(narrow_state, "topic", () => "foo");

    message_lists.current.data.fetch_status.finish_newer_batch([], {
        update_loading_indicator: false,
        found_newest: false,
    });
    message_lists.current.data.fetch_status.finish_older_batch({
        update_loading_indicator: false,
        found_oldest: false,
        history_limited: false,
    });

    assert.ok(!message_lists.current.data.fetch_status.has_found_newest());
    assert.ok(!message_lists.current.data.fetch_status.has_found_oldest());

    stream_popover.update_move_messages_count_text(
        "change_later",
        rome_sub.stream_id,
        "foo",
        selected_message_id,
    );
    assert.equal($("#move_messages_count").text(), "translated: 2+ messages will be moved.");

    // Case 3: selected_option === "change_all"

    // This is the general case when we are in topic narrow.
    override(narrow_state, "narrowed_by_topic_reply", () => true);
    override(narrow_state, "narrowed_by_stream_reply", () => false);
    override(narrow_state, "stream_id", () => rome_sub.stream_id);
    override(narrow_state, "topic", () => "foo");

    message_lists.current.data.fetch_status.finish_newer_batch([], {
        update_loading_indicator: false,
        found_newest: true,
    });
    message_lists.current.data.fetch_status.finish_older_batch({
        update_loading_indicator: false,
        found_oldest: true,
        history_limited: false,
    });

    assert.ok(message_lists.current.data.fetch_status.has_found_newest());
    assert.ok(message_lists.current.data.fetch_status.has_found_oldest());

    stream_popover.update_move_messages_count_text("change_all", rome_sub.stream_id, "foo");
    assert.equal($("#move_messages_count").text(), "translated: 3 messages will be moved.");

    // This is case when we are in stream narrow and the topic is not the same.
    override(narrow_state, "narrowed_by_topic_reply", () => true);
    override(narrow_state, "narrowed_by_stream_reply", () => false);
    override(narrow_state, "stream_id", () => rome_sub.stream_id);
    override(narrow_state, "topic", () => "boo");

    message_lists.current.data.fetch_status.finish_newer_batch([], {
        update_loading_indicator: false,
        found_newest: false,
    });
    message_lists.current.data.fetch_status.finish_older_batch({
        update_loading_indicator: false,
        found_oldest: false,
        history_limited: false,
    });

    assert.ok(!message_lists.current.data.fetch_status.has_found_newest());
    assert.ok(!message_lists.current.data.fetch_status.has_found_oldest());

    stream_popover.update_move_messages_count_text("change_all", rome_sub.stream_id, "foo");
    assert.equal($("#move_messages_count").text(), "translated: 3+ messages will be moved.");

    // This is the case when we are in an interleaved view.
    override(narrow_state, "narrowed_by_topic_reply", () => false);
    override(narrow_state, "narrowed_by_stream_reply", () => false);
    override(narrow_state, "stream_id", () => rome_sub.stream_id);
    override(narrow_state, "topic", () => "foo");

    message_lists.current.data.fetch_status.finish_newer_batch([], {
        update_loading_indicator: false,
        found_newest: false,
    });
    message_lists.current.data.fetch_status.finish_older_batch({
        update_loading_indicator: false,
        found_oldest: false,
        history_limited: false,
    });

    assert.ok(!message_lists.current.data.fetch_status.has_found_newest());
    assert.ok(!message_lists.current.data.fetch_status.has_found_oldest());

    stream_popover.update_move_messages_count_text("change_all", rome_sub.stream_id, "foo");
    assert.equal($("#move_messages_count").text(), "translated: 3+ messages will be moved.");
});
