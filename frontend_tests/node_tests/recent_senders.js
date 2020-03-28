const rs = zrequire('recent_senders');

let next_id = 0;

run_test('process_message_for_senders', () => {
    const stream1 = 1;
    const stream2 = 2;
    const stream3 = 3;

    const topic1 = "topic-1";
    const topic2 = "topic-2";
    const topic3 = "topic-3";

    const sender1 = 1;
    const sender2 = 2;
    const sender3 = 3;

    // New stream
    const message1 = {
        stream_id: stream1,
        id: next_id += 1,
        topic: topic1,
        sender_id: sender1,
    };
    const message2 = {
        stream_id: stream2,
        id: next_id += 1,
        topic: topic1,
        sender_id: sender2,
    };
    rs.process_message_for_senders(message1);
    rs.process_message_for_senders(message2);

    // Users have posted in only one of the streams
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream2, topic1) > 0,
        true);

    // Users haven't posted in this stream, return zero
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream3, undefined) === 0,
        true);

    // New topic
    const message3 = {
        stream_id: stream1,
        id: next_id += 1,
        topic: topic2,
        sender_id: sender3,
    };
    rs.process_message_for_senders(message3);
    assert.equal(
        rs.compare_by_recency({user_id: sender3}, {user_id: sender2}, stream1, topic2) < 0,
        true);

    // New sender
    const message4 = {
        stream_id: stream1,
        id: next_id += 1,
        topic: topic1,
        sender_id: sender2,
    };
    rs.process_message_for_senders(message4);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) > 0,
        true);

    // More recent message
    const message5 = {
        stream_id: stream1,
        id: next_id += 1,
        topic: topic1,
        sender_id: sender1,
    };
    rs.process_message_for_senders(message5);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true);

    // Same stream, but different topics
    const message6 = {
        stream_id: stream3,
        id: next_id += 1,
        topic: topic1,
        sender_id: sender1,
    };
    const message7 = {
        stream_id: stream3,
        id: next_id += 1,
        topic: topic2,
        sender_id: sender2,
    };
    const message8 = {
        stream_id: stream3,
        id: next_id += 1,
        topic: topic3,
        sender_id: sender3,
    };

    rs.process_message_for_senders(message6);
    rs.process_message_for_senders(message7);
    rs.process_message_for_senders(message8);

    // topic3 has a message in it, but sender1 nor sender2 have participated, so sort by stream
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream3, topic3) > 0,
        true);
    assert.equal(
        rs.compare_by_recency({user_id: sender2}, {user_id: sender1}, stream3, topic3) < 0,
        true);

    assert.equal(rs.compare_by_recency({}, {}, next_id += 1, ''), 0);
});
