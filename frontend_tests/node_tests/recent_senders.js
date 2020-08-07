"use strict";

const rs = zrequire("recent_senders");

let next_id = 0;
const messages = [];

set_global("message_store", {
    get: (msg_id) => messages[msg_id - 1],
});
set_global("message_list", {
    all: {
        all_messages() {
            return messages;
        },
    },
});
zrequire("message_util.js");
run_test("process_message_for_senders", () => {
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
    const message1 = {
        type: "stream",
        stream_id: stream1,
        id: (next_id += 1),
        topic: topic1,
        sender_id: sender1,
    };
    const message2 = {
        type: "stream",
        stream_id: stream2,
        id: (next_id += 1),
        topic: topic1,
        sender_id: sender2,
    };
    messages.push(message1, message2);

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
    const message3 = {
        type: "stream",
        stream_id: stream1,
        id: (next_id += 1),
        topic: topic2,
        sender_id: sender3,
    };
    messages.push(message3);

    rs.process_message_for_senders(message3);
    assert.equal(
        rs.compare_by_recency({user_id: sender3}, {user_id: sender2}, stream1, topic2) < 0,
        true,
    );

    // New sender
    const message4 = {
        type: "stream",
        stream_id: stream1,
        id: (next_id += 1),
        topic: topic1,
        sender_id: sender2,
    };
    messages.push(message4);

    rs.process_message_for_senders(message4);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) > 0,
        true,
    );

    // More recent message
    const message5 = {
        type: "stream",
        stream_id: stream1,
        id: (next_id += 1),
        topic: topic1,
        sender_id: sender1,
    };
    messages.push(message5);

    rs.process_message_for_senders(message5);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true,
    );

    // Same stream, but different topics
    const message6 = {
        type: "stream",
        stream_id: stream3,
        id: (next_id += 1),
        topic: topic1,
        sender_id: sender1,
    };
    const message7 = {
        type: "stream",
        stream_id: stream3,
        id: (next_id += 1),
        topic: topic2,
        sender_id: sender2,
    };
    const message8 = {
        type: "stream",
        stream_id: stream3,
        id: (next_id += 1),
        topic: topic3,
        sender_id: sender3,
    };
    messages.push(message6, message7, message8);

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
    const message9 = {
        type: "stream",
        stream_id: stream3,
        id: (next_id += 1),
        topic: topic2,
        sender_id: sender3,
    };
    messages.push(message9);

    rs.process_message_for_senders(message9);

    // Test topic change
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "3");
    assert.equal(rs.get_topic_recent_senders(stream3, topic2).toString(), "2,3");

    // message7's topic was changed by user
    messages[6].topic = topic3;

    rs.process_topic_edit(stream3, topic2, topic3);
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "2,3");
    assert.equal(rs.get_topic_recent_senders(stream3, topic2).toString(), "3");

    // Test stream change
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "2,3");
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "");
    // stream of topic3 was changed to stream4.
    messages[6].stream_id = stream4; // message7's topic is topic3
    messages[7].stream_id = stream4;
    rs.process_topic_edit(stream3, topic3, topic3, stream4);
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "2,3");

    // Test stream & topic change
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "2,3");
    assert.equal(rs.get_topic_recent_senders(stream5, topic4).toString(), "");
    // stream of topic3 was changed to stream5 and topic was changed to topic4.
    messages[6].stream_id = stream5;
    messages[7].stream_id = stream5;
    messages[6].topic = topic4;
    messages[7].topic = topic4;
    rs.process_topic_edit(stream4, topic3, topic4, stream5);
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream5, topic4).toString(), "2,3");

    set_global("message_list", {
        all: {
            all_messages() {
                // messages[0] (message1) and messages[4] (message5) were removed.
                const reduced_msgs = [...messages];
                reduced_msgs.splice(4, 1);
                reduced_msgs.splice(0, 1);
                return reduced_msgs;
            },
        },
    });
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "2,1");
    // delete message1 and message5 sent by sender1
    rs.update_topics_of_deleted_message_ids([message1.id, message5.id]);
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "2");

    // deleting an old message which isn't locally stored.
    // We are just testing that it doesn't raise an error;
    // no changes should take place in this case.
    rs.update_topics_of_deleted_message_ids([-1]);
});
