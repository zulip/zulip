var assert = require('assert');
var rs = require('js/recent_senders.js');
var _ = require('node_modules/underscore/underscore.js');

(function test_process_message_for_senders() {
    var stream1 = 1;
    var stream2 = 2;
    var stream3 = 3;

    var topic1 = "topic-1";
    var topic2 = "topic-2";
    var topic3 = "topic-3";

    var sender1 = 1;
    var sender2 = 2;
    var sender3 = 3;

    // New stream
    var message1 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender1,
    };
    var message2 = {
        stream_id: stream2,
        timestamp: _.uniqueId(),
        subject: topic1,
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
    var message3 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic2,
        sender_id: sender3,
    };
    rs.process_message_for_senders(message3);
    assert.equal(
        rs.compare_by_recency({user_id: sender3}, {user_id: sender2}, stream1, topic2) < 0,
        true);

    // New sender
    var message4 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender2,
    };
    rs.process_message_for_senders(message4);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) > 0,
        true);

    // More recent message
    var message5 = {
        stream_id: stream1,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender1,
    };
    rs.process_message_for_senders(message5);
    assert.equal(
        rs.compare_by_recency({user_id: sender1}, {user_id: sender2}, stream1, topic1) < 0,
        true);

    // Same stream, but different topics
    var message6 = {
        stream_id: stream3,
        timestamp: _.uniqueId(),
        subject: topic1,
        sender_id: sender1,
    };
    var message7 = {
        stream_id: stream3,
        timestamp: _.uniqueId(),
        subject: topic2,
        sender_id: sender2,
    };
    var message8 = {
        stream_id: stream3,
        timestamp: _.uniqueId(),
        subject: topic3,
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

    assert.equal(rs.compare_by_recency({}, {}, _.uniqueId(), ''), 0);
}());
