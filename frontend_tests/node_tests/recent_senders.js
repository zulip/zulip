"use strict";

const {strict: assert} = require("assert");

const {mock_module, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

let next_id = 0;
const messages = new Map();

function make_stream_message({stream_id, topic, sender_id}) {
    next_id += 1;

    const message = {
        type: "stream",
        stream_id,
        id: next_id,
        topic,
        sender_id,
    };
    messages.set(message.id, message);

    return message;
}

const message_list = mock_module("message_list", {
    all: {
        all_messages() {
            return Array.from(messages.values());
        },
    },
});
mock_module("message_store", {
    get: (message_id) => messages.get(message_id),
});

const rs = zrequire("recent_senders");
zrequire("message_util.js");

function test(label, f) {
    run_test(label, (override) => {
        messages.clear();
        next_id = 0;
        rs.clear_for_testing();
        f(override);
    });
}

test("process_message_for_senders", (override) => {
    const stream1 = 1;
    const stream2 = 2;
    const stream3 = 3;

    const topic1 = "topic-1";
    const topic2 = "topic-2";
    const topic3 = "topic-3";
    const topic4 = "topic-4";

    const sender1 = 1;
    const sender2 = 2;
    const sender3 = 3;
    const stream4 = 4;
    const stream5 = 5;

    // New stream
    const message1 = make_stream_message({
        stream_id: stream1,
        topic: topic1,
        sender_id: sender1,
    });

    const message2 = make_stream_message({
        stream_id: stream2,
        topic: topic1,
        sender_id: sender2,
    });

    rs.process_message_for_senders(message1);
    rs.process_message_for_senders(message2);

    // Users have posted in only one of the streams
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true,
    );
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream2, topic1) > 0,
        true,
    );

    // Users haven't posted in this stream, return zero
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream3, undefined) === 0,
        true,
    );

    // New topic
    const message3 = make_stream_message({
        stream_id: stream1,
        topic: topic2,
        sender_id: sender3,
    });

    rs.process_message_for_senders(message3);
    assert.equal(
        rs.compare_by_recency({user_id: sender3}, {user_id: sender2}, stream1, topic2) < 0,
        true,
    );

    // New sender
    const message4 = make_stream_message({
        stream_id: stream1,
        topic: topic1,
        sender_id: sender2,
    });

    rs.process_message_for_senders(message4);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) > 0,
        true,
    );

    // More recent message
    const message5 = make_stream_message({
        stream_id: stream1,
        topic: topic1,
        sender_id: sender1,
    });

    rs.process_message_for_senders(message5);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true,
    );

    // Same stream, but different topics
    const message6 = make_stream_message({
        stream_id: stream3,
        topic: topic1,
        sender_id: sender1,
    });
    const message7 = make_stream_message({
        stream_id: stream3,
        topic: topic2,
        sender_id: sender2,
    });
    const message8 = make_stream_message({
        stream_id: stream3,
        topic: topic3,
        sender_id: sender3,
    });

    rs.process_message_for_senders(message6);
    rs.process_message_for_senders(message7);
    rs.process_message_for_senders(message8);

    // topic3 has a message in it, but sender1 nor sender2 have participated, so sort by stream
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream3, topic3) > 0,
        true,
    );
    assert.equal(
        rs.compare_by_recency({user_id: sender2}, {user_id: sender1}, stream3, topic3) < 0,
        true,
    );

    assert.equal(rs.compare_by_recency({}, {}, (next_id += 1), ""), 0);

    // new message in topic2
    const message9 = make_stream_message({
        stream_id: stream3,
        topic: topic2,
        sender_id: sender3,
    });

    rs.process_message_for_senders(message9);

    // Test topic change
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "3");
    assert.equal(rs.get_topic_recent_senders(stream3, topic2).toString(), "2,3");

    // message7's topic was changed by user
    message7.topic = topic3;

    rs.process_topic_edit(stream3, topic2, topic3);
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "2,3");
    assert.equal(rs.get_topic_recent_senders(stream3, topic2).toString(), "3");

    // Test stream change
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "2,3");
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "");
    // stream of topic3 was changed to stream4.
    message7.stream_id = stream4; // message7's topic is topic3
    message8.stream_id = stream4;
    rs.process_topic_edit(stream3, topic3, topic3, stream4);
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "2,3");

    // Test stream & topic change
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "2,3");
    assert.equal(rs.get_topic_recent_senders(stream5, topic4).toString(), "");
    // stream of topic3 was changed to stream5 and topic was changed to topic4.
    message7.stream_id = stream5;
    message8.stream_id = stream5;
    message7.topic = topic4;
    message8.topic = topic4;
    rs.process_topic_edit(stream4, topic3, topic4, stream5);
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream5, topic4).toString(), "2,3");

    const reduced_msgs = [message3, message4, message7, message8];

    override(message_list.all, "all_messages", () => reduced_msgs);
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "2,1");
    // delete message1 and message5 sent by sender1
    rs.update_topics_of_deleted_message_ids([message1.id, message5.id]);
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "2");

    // deleting an old message which isn't locally stored.
    // We are just testing that it doesn't raise an error;
    // no changes should take place in this case.
    rs.update_topics_of_deleted_message_ids([-1]);
});
