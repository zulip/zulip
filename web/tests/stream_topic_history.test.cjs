"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");

const channel = mock_esm("../src/channel");
const message_util = mock_esm("../src/message_util");

const echo_state = zrequire("echo_state");
const topic_list = zrequire("topic_list");
const unread = zrequire("unread");
const message_store = zrequire("message_store");
const {set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_topic_history = zrequire("stream_topic_history");
const stream_topic_history_util = zrequire("stream_topic_history_util");

set_realm({});

stream_topic_history.set_update_topic_last_message_id(noop);

function test(label, f) {
    run_test(label, (helpers) => {
        unread.declare_bankruptcy();
        stream_topic_history.reset();
        f(helpers);
    });
}

test("basics", () => {
    const stream_id = 55;

    stream_topic_history.add_message({
        stream_id,
        message_id: 101,
        topic_name: "toPic1",
    });

    let history = stream_topic_history.get_recent_topic_names(stream_id);
    let max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(history, ["toPic1"]);
    assert.deepEqual(max_message_id, 101);

    stream_topic_history.add_message({
        stream_id,
        message_id: 102,
        topic_name: "Topic1",
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(history, ["Topic1"]);
    assert.deepEqual(max_message_id, 102);

    stream_topic_history.add_message({
        stream_id,
        message_id: 103,
        topic_name: "topic2",
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(history, ["topic2", "Topic1"]);
    assert.deepEqual(max_message_id, 103);

    stream_topic_history.add_message({
        stream_id,
        message_id: 104,
        topic_name: "Topic1",
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(history, ["Topic1", "topic2"]);
    assert.deepEqual(max_message_id, 104);

    message_util.get_loaded_messages_in_topic = () => [{id: 101}, {id: 102}];
    message_util.get_max_message_id_in_stream = () => 103;
    // Removing the last msg in topic1 changes the order
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "Topic1",
        num_messages: 1,
        max_removed_msg_id: 104,
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["topic2", "Topic1"]);
    // check if stream's max_message_id is updated.
    max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(max_message_id, 103);

    delete message_util.get_loaded_messages_in_topic;
    // Removing first topic1 message has no effect.
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "toPic1",
        num_messages: 1,
        max_removed_msg_id: 101,
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["topic2", "Topic1"]);
    max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(max_message_id, 103);

    // Removing second topic1 message removes the topic.
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "Topic1",
        num_messages: 1,
        max_removed_msg_id: 102,
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["topic2"]);

    // Test that duplicate remove does not crash us.
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "Topic1",
        num_messages: 1,
        max_removed_msg_id: 0,
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["topic2"]);

    // get to 100% coverage for defensive code
    stream_topic_history.remove_messages({
        stream_id: 9999999,
        num_messages: 1,
    });
});

test("server_history", () => {
    const sub = {
        name: "devel",
        stream_id: 66,
    };
    const stream_id = sub.stream_id;
    stream_data.add_sub(sub);

    assert.equal(topic_list.is_full_topic_history_available(stream_id), false);

    stream_topic_history.add_message({
        stream_id,
        message_id: 501,
        topic_name: "local",
    });

    function add_server_history() {
        stream_topic_history.add_history(stream_id, [
            {name: "local", max_id: 501},
            {name: "hist2", max_id: 31},
            {name: "hist1", max_id: 30},
        ]);
    }

    add_server_history();

    // Since we added history, now subsequent calls
    // to is_full_topic_history_available will return true.
    assert.equal(topic_list.is_full_topic_history_available(stream_id), true);

    let history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["local", "hist2", "hist1"]);

    // If new activity comes in for historical messages,
    // they can bump to the front of the list.
    stream_topic_history.add_message({
        stream_id,
        message_id: 502,
        topic_name: "hist1",
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["hist1", "local", "hist2"]);

    // server history is allowed to backdate hist1
    add_server_history();
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["local", "hist2", "hist1"]);

    // Removing a local message removes the topic if we have
    // our counts right.
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "local",
        num_messages: 1,
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["hist2", "hist1"]);

    // Removing message from a topic fetched from server history, will send
    // query to the server to get the latest message id in the topic.
    let update_topic_called = false;
    stream_topic_history.set_update_topic_last_message_id((stream_id, topic_name) => {
        assert.equal(stream_id, 66);
        assert.equal(topic_name, "hist2");
        update_topic_called = true;
    });
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "hist2",
        num_messages: 1,
    });
    assert.equal(update_topic_called, true);
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["hist1"]);
    stream_topic_history.set_update_topic_last_message_id(noop);

    // If we call back to the server for history, the
    // effect is always additive.  We may decide to prune old
    // topics in the future, if they dropped off due to renames,
    // but that is probably an edge case we can ignore for now.
    stream_topic_history.add_history(stream_id, [
        {name: "hist2", max_id: 931},
        {name: "hist3", max_id: 5},
    ]);
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["hist2", "hist1", "hist3"]);
});

test("test_unread_logic", () => {
    const stream_id = 77;

    stream_topic_history.add_message({
        stream_id,
        message_id: 201,
        topic_name: "toPic1",
    });

    stream_topic_history.add_message({
        stream_id,
        message_id: 45,
        topic_name: "topic2",
    });

    let history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["toPic1", "topic2"]);

    const msgs = [
        // This will be ignored as a case variant of `topic2` above.
        {id: 150, topic: "TOPIC2"},
        {id: 61, topic: "unread1"},
        {id: 60, topic: "unread1"},
        {id: 20, topic: "UNREAD2"},
        // We're going to mark this as read; this will verify the logic
        // in unreads.js for only including topics with nonzero unreads.
        {id: 79, topic: "to_mark_as_read"},
    ];

    for (const msg of msgs) {
        msg.type = "stream";
        msg.stream_id = stream_id;
        msg.unread = true;
        message_store.update_message_cache(msg);
    }

    unread.process_loaded_messages(msgs);
    unread.mark_as_read(79);

    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["toPic1", "unread1", "topic2", "UNREAD2"]);
});

test("test_stream_has_topics", () => {
    const stream_id = 88;

    assert.equal(stream_topic_history.stream_has_topics(stream_id), false);
    assert.equal(stream_topic_history.stream_has_locally_available_named_topics(stream_id), false);

    stream_topic_history.find_or_create(stream_id);

    // This was a bug before--just creating a bucket does not
    // mean we have actual topics.
    assert.equal(stream_topic_history.stream_has_topics(stream_id), false);

    stream_topic_history.add_message({
        stream_id,
        message_id: 888,
        topic_name: "",
    });

    assert.equal(stream_topic_history.stream_has_topics(stream_id), true);
    assert.equal(stream_topic_history.stream_has_locally_available_named_topics(stream_id), false);

    stream_topic_history.add_message({
        stream_id,
        message_id: 888,
        topic_name: "whatever",
    });

    assert.equal(stream_topic_history.stream_has_topics(stream_id), true);
    assert.equal(stream_topic_history.stream_has_locally_available_named_topics(stream_id), true);
});

test("test_stream_has_resolved_topics", () => {
    const stream_id = 89;

    assert.equal(
        stream_topic_history.stream_has_locally_available_resolved_topics(stream_id),
        false,
    );

    stream_topic_history.add_message({
        stream_id,
        message_id: 889,
        topic_name: "✔ whatever",
    });

    assert.equal(
        stream_topic_history.stream_has_locally_available_resolved_topics(stream_id),
        true,
    );
});

test("server_history_end_to_end", () => {
    stream_topic_history.reset();

    const stream_id = 99;

    const topics = [
        {name: "topic3", max_id: 501},
        {name: "topic2", max_id: 31},
        {name: "topic1", max_id: 30},
    ];

    let get_success_callback;
    let on_success_called;

    channel.get = (opts) => {
        assert.equal(opts.url, "/json/users/me/99/topics");
        assert.deepEqual(opts.data, {allow_empty_topic_name: true});
        assert.ok(stream_topic_history.is_request_pending_for(stream_id));
        get_success_callback = opts.success;
    };

    stream_topic_history_util.get_server_history(stream_id, noop);

    // Another call. Early return because a request is already in progress
    // for stream_id = 99. This function call adds coverage.
    stream_topic_history_util.get_server_history(stream_id, noop);
    assert.ok(stream_topic_history.is_request_pending_for(stream_id));

    stream_topic_history_util.get_server_history(stream_id, () => {
        on_success_called = true;
    });

    get_success_callback({topics});
    assert.ok(on_success_called);
    assert.ok(!stream_topic_history.is_request_pending_for(stream_id));

    const history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["topic3", "topic2", "topic1"]);

    for (const topic of topics) {
        const last_msg_id_in_topic = stream_topic_history.get_latest_known_message_id_in_topic(
            stream_id,
            topic.name,
        );
        assert.deepEqual(last_msg_id_in_topic, topic.max_id);
    }

    // Try getting server history for a second time.

    /* istanbul ignore next */
    channel.get = () => {
        throw new Error("We should not get more data.");
    };

    on_success_called = false;
    stream_topic_history_util.get_server_history(stream_id, () => {
        on_success_called = true;
    });
    assert.ok(on_success_called);
});

test("server_history_error", () => {
    set_global("setTimeout", (f) => {
        f();
    });
    stream_topic_history.reset();

    const channel_id = 99;

    let total_attempts = 0;
    channel.get = (opts) => {
        assert.equal(opts.url, "/json/users/me/99/topics");
        assert.ok(stream_topic_history.is_request_pending_for(channel_id));
        // This mocks error on each GET request.
        opts.error();
        total_attempts += 1;
    };

    stream_topic_history_util.get_server_history(channel_id, noop);
    // Verify that we stop after MAX_RETRIES attempt.
    assert.deepEqual(total_attempts, stream_topic_history_util.MAX_RETRIES);
    assert.ok(!stream_topic_history.is_request_pending_for(channel_id));
});

test("ask_server_for_latest_topic_data", () => {
    stream_topic_history.set_update_topic_last_message_id((stream_id, topic_name) => {
        stream_topic_history_util.update_topic_last_message_id(stream_id, topic_name, noop);
    });
    const stream_id = 1080;

    let success_callback;
    let get_message_request_triggered = false;
    channel.get = (opts) => {
        get_message_request_triggered = true;
        assert.equal(opts.url, "/json/messages");
        assert.deepEqual(opts.data, {
            anchor: "newest",
            narrow: '[{"operator":"stream","operand":1080},{"operator":"topic","operand":"Topic1"}]',
            num_after: 0,
            num_before: 1,
            allow_empty_topic_name: true,
        });
        success_callback = opts.success;
    };

    stream_topic_history.add_message({
        stream_id,
        message_id: 101,
        topic_name: "topic1",
    });

    let history = stream_topic_history.get_recent_topic_names(stream_id);
    let max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(history, ["topic1"]);
    assert.deepEqual(max_message_id, 101);

    // Remove all cached messages from the topic. This sends a request to the server
    // to check for the latest message id in the topic.
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "Topic1",
        num_messages: 1,
        max_removed_msg_id: 104,
    });
    assert.equal(get_message_request_triggered, true);
    get_message_request_triggered = false;

    // Until we process the response from the server,
    // the topic is not available.
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, []);

    // Simulate the server responses.
    // Topic is empty.
    success_callback({
        messages: [],
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, []);

    // Topic has a different max_message_id.
    success_callback({
        messages: [{id: 102}],
    });

    // The topic is now available.
    history = stream_topic_history.get_recent_topic_names(stream_id);
    max_message_id = stream_topic_history.get_max_message_id(stream_id);
    assert.deepEqual(history, ["Topic1"]);
    assert.deepEqual(max_message_id, 102);
});

// Test when a local unacked message is sent, then get_max_message_id would also
// consider this unacked message. However, the unacked message is not added to
// max_message_id of stream, or message_id of topic histories.
test("test_max_message_ids_in_channel_and_topics", () => {
    const general_sub = {
        stream_id: 101,
        name: "general",
        subscribed: true,
    };

    const history = stream_topic_history.find_or_create(general_sub.stream_id);

    stream_topic_history.add_message({
        stream_id: general_sub.stream_id,
        message_id: 45,
        topic_name: "topic 1",
    });

    assert.equal(stream_topic_history.get_max_message_id(general_sub.stream_id), 45);
    assert.equal(history.max_message_id, 45);

    stream_topic_history.add_message({
        stream_id: general_sub.stream_id,
        message_id: 47,
        topic_name: "topic 1",
    });

    assert.equal(stream_topic_history.get_max_message_id(general_sub.stream_id), 47);
    assert.equal(history.max_message_id, 47);

    const local_message = {
        type: "stream",
        stream_id: general_sub.stream_id,
        topic: "topic 2",
        sender_email: "iago@zulip.com",
        sender_full_name: "Iago",
        sender_id: 123,
        id: 49.01,
    };
    echo_state.set_message_waiting_for_ack("49.01", local_message);

    assert.equal(stream_topic_history.get_max_message_id(general_sub.stream_id), 49.01);
    assert.equal(history.max_message_id, 47);
    assert.equal(history.topics.get("topic 2"), undefined);

    assert.deepEqual(stream_topic_history.get_recent_topic_names(general_sub.stream_id), [
        "topic 2",
        "topic 1",
    ]);
});

test("remove_history_for_stream", () => {
    const stream_id = 55;
    stream_topic_history.add_message({
        stream_id,
        message_id: 101,
        topic_name: "toPic1",
    });

    stream_topic_history.add_message({
        stream_id: 56,
        message_id: 102,
        topic_name: "topic2",
    });
    assert.equal(stream_topic_history.stream_has_topics(stream_id), true);
    assert.equal(stream_topic_history.stream_has_topics(56), true);

    stream_topic_history.remove_history_for_stream(stream_id);
    assert.equal(stream_topic_history.stream_has_topics(stream_id), false);
    assert.equal(stream_topic_history.stream_has_topics(56), true);

    stream_topic_history.add_history(stream_id, [
        {name: "local", max_id: 501},
        {name: "hist2", max_id: 31},
        {name: "hist1", max_id: 30},
    ]);
    assert.equal(stream_topic_history.has_history_for(stream_id), true);
    assert.equal(stream_topic_history.stream_has_topics(stream_id), true);

    stream_topic_history.remove_history_for_stream(stream_id);
    assert.equal(stream_topic_history.stream_has_topics(stream_id), false);
    assert.equal(stream_topic_history.has_history_for(stream_id), false);
});
