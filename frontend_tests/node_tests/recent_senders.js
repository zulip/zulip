var rs = zrequire('recent_senders');

(function test_process_message_for_senders() {
    var stream1 = 1;
    var stream2 = 2;
    var stream3 = 3;

    var topic1 = "topic-1";
    var topic2 = "topic-2";
    var topic3 = "topic-3";

    var sender1 = 1;
    var sender2 = 2;
    var sender3 = 3;    // This is used to post a message in an empty topic/stream.

// No one has posted in organisation
assert.equal(
    rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1),
    0);

// Only one person has posted in the orgainsation
    var message1 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender1,
    };
    rs.process_message_for_senders(message1);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic2) < 0,
        true);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream2, topic1) < 0,
        true);


// When recency is checked on the basis of topic:

    // Both have posted in current stream and topic.
    var message2 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender2,
    };
    rs.process_message_for_senders(message2);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) > 0,
        true);

    var message3 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender1,
    };
    rs.process_message_for_senders(message3);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true);
    var message4 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic2,
        sender_id: sender2,
    };
    rs.process_message_for_senders(message4);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true);

    // Both have posted in current stream but only one has posted in the current topic.
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic2) > 0,
        true);

    //  Only one has posted in current stream and topic.
    var message5 = {
        stream_id: stream2,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender1,
    };
    rs.process_message_for_senders(message5);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream2, topic1) < 0,
        true);


// When recency is checked on the basis of the whole stream.

    // Both have posted in current stream but no one has posted in the current topic.
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic3) > 0,
        true);
    var message6 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic3,
        sender_id: sender3,
    };
    rs.process_message_for_senders(message6);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic3) > 0,
        true);

    // Only one has posted in current stream but no one has posted in the current topic.
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream2, topic2) < 0,
        true);
    var message7 = {
        stream_id: stream2,
        timestamp: _.uniqueId(),
        subject: topic2,
        sender_id: sender3,
    };
    rs.process_message_for_senders(message7);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream2, topic2) < 0,
        true);


// When recency is checked on the basis of the recent message in the whole organization.

    // Neither of them has posted in the current stream.
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream3, topic1) < 0,
        true);
    var message8 = {
        stream_id: stream3,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender3,
    };
    rs.process_message_for_senders(message8);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream3, topic1) < 0,
        true);
}());
