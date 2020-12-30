"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

zrequire("unread");
zrequire("stream_data");
zrequire("stream_topic_history");

set_global("channel", {});
set_global("message_list", {});

run_test("basics", () => {
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

    set_global("message_util", {
        get_messages_in_topic: () => [{id: 101}, {id: 102}],
        get_max_message_id_in_stream: () => 103,
    });
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

    set_global("message_util", {
        get_messages_in_topic: () => [{id: 102}],
        get_max_message_id_in_stream: () => 103,
    });
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

run_test("is_complete_for_stream_id", () => {
    const sub = {
        name: "devel",
        stream_id: 444,
        first_message_id: 1000,
    };
    stream_data.add_sub(sub);

    message_list.all = {
        empty: () => false,
        data: {
            fetch_status: {
                has_found_newest: () => true,
            },
        },
        first: () => ({id: 5}),
    };

    assert.equal(stream_topic_history.is_complete_for_stream_id(sub.stream_id), true);

    // Now simulate a more recent message id.
    message_list.all.first = () => ({id: sub.first_message_id + 1});

    // Note that we'll return `true` here due to
    // fetched_stream_ids having the stream_id now.
    assert.equal(stream_topic_history.is_complete_for_stream_id(sub.stream_id), true);

    // But now clear the data to see what we'd have without
    // the previous call.
    stream_topic_history.reset();

    assert.equal(stream_topic_history.is_complete_for_stream_id(sub.stream_id), false);
});

run_test("server_history", () => {
    const sub = {
        name: "devel",
        stream_id: 66,
    };
    const stream_id = sub.stream_id;
    stream_data.add_sub(sub);

    message_list.all.data.fetch_status.has_found_newest = () => false;

    assert.equal(stream_topic_history.is_complete_for_stream_id(stream_id), false);

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
    // to is_complete_for_stream_id will return true.
    assert.equal(stream_topic_history.is_complete_for_stream_id(stream_id), true);

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

    // We can try to remove a historical message, but it should
    // have no effect.
    stream_topic_history.remove_messages({
        stream_id,
        topic_name: "hist2",
        num_messages: 1,
    });
    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["hist2", "hist1"]);

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

run_test("test_unread_logic", () => {
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
        {id: 150, topic: "TOPIC2"}, // will be ignored
        {id: 61, topic: "unread1"},
        {id: 60, topic: "unread1"},
        {id: 20, topic: "UNREAD2"},
    ];

    for (const msg of msgs) {
        msg.type = "stream";
        msg.stream_id = stream_id;
        msg.unread = true;
    }

    unread.process_loaded_messages(msgs);

    history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["toPic1", "unread1", "topic2", "UNREAD2"]);
});

run_test("test_stream_has_topics", () => {
    const stream_id = 88;

    assert.equal(stream_topic_history.stream_has_topics(stream_id), false);

    stream_topic_history.find_or_create(stream_id);

    // This was a bug before--just creating a bucket does not
    // mean we have actual topics.
    assert.equal(stream_topic_history.stream_has_topics(stream_id), false);

    stream_topic_history.add_message({
        stream_id,
        message_id: 888,
        topic_name: "whatever",
    });

    assert.equal(stream_topic_history.stream_has_topics(stream_id), true);
});

run_test("server_history_end_to_end", () => {
    stream_topic_history.reset();

    const stream_id = 99;

    const topics = [
        {name: "topic3", max_id: 501},
        {name: "topic2", max_id: 31},
        {name: "topic1", max_id: 30},
    ];

    let get_success_callback;
    let on_success_called;

    channel.get = function (opts) {
        assert.equal(opts.url, "/json/users/me/99/topics");
        assert.deepEqual(opts.data, {});
        get_success_callback = opts.success;
    };

    stream_topic_history.get_server_history(stream_id, () => {
        on_success_called = true;
    });

    get_success_callback({topics});

    assert(on_success_called);

    const history = stream_topic_history.get_recent_topic_names(stream_id);
    assert.deepEqual(history, ["topic3", "topic2", "topic1"]);

    // Try getting server history for a second time.

    channel.get = () => {
        throw new Error("We should not get more data.");
    };

    on_success_called = false;
    stream_topic_history.get_server_history(stream_id, () => {
        on_success_called = true;
    });
    assert(on_success_called);
});
