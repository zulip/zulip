"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
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

mock_esm("../../static/js/message_store", {
    get: (message_id) => messages.get(message_id),
});
const people = zrequire("people");
people.initialize_current_user(1);
const rs = zrequire("recent_senders");
zrequire("message_util.js");

function test(label, f) {
    run_test(label, ({override}) => {
        messages.clear();
        next_id = 0;
        rs.clear_for_testing();
        f({override});
    });
}

test("IdTracker", () => {
    const id_tracker = new rs.IdTracker();

    function test_add(id, expected_max_id) {
        id_tracker.add(id);
        assert.equal(id_tracker.max_id(), expected_max_id);
    }

    test_add(5, 5);
    test_add(7, 7);
    test_add(3, 7);
    test_add(10, 10);
    test_add(12, 12);
    test_add(11, 12);

    function test_remove(id, expected_max_id) {
        id_tracker.remove(id);
        assert.equal(id_tracker.max_id(), expected_max_id);
    }

    test_remove(10, 12);
    test_remove(999999, 12); // bogus id has no effect
    test_remove(3, 12);
    test_remove(12, 11);

    test_add(3, 11);
    test_add(7, 11);
    test_add(13, 13);

    test_remove(3, 13);
    test_remove(13, 11);
});

test("noop process_topic_edit", () => {
    // Just get line coverage on defensive code.
    const bogus_ids = [333, 444];
    rs.process_topic_edit({message_ids: bogus_ids});
});

test("update_topics_of_deleted_message_ids", () => {
    // Just get line coverage on defensive code.
    const stream_id = 555;
    const topic = "whatever";
    const sender_id = 999;

    const message = make_stream_message({
        stream_id,
        topic,
        sender_id,
    });
    rs.update_topics_of_deleted_message_ids([message.id]);
    assert.deepEqual(rs.get_topic_recent_senders(stream_id, topic), []);

    rs.process_stream_message(message);
    assert.deepEqual(rs.get_topic_recent_senders(stream_id, topic), [sender_id]);
});

test("process_stream_message", () => {
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

    rs.process_stream_message(message1);
    rs.process_stream_message(message2);

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

    rs.process_stream_message(message3);
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

    rs.process_stream_message(message4);
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

    rs.process_stream_message(message5);
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

    rs.process_stream_message(message6);
    rs.process_stream_message(message7);
    rs.process_stream_message(message8);

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

    rs.process_stream_message(message9);

    // Test topic change
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "3");
    assert.equal(rs.get_topic_recent_senders(stream3, topic2).toString(), "3,2");

    // message7's topic was changed by user
    message7.topic = topic3;

    rs.process_topic_edit({
        message_ids: [message7.id],
        old_stream_id: stream3,
        new_stream_id: stream3,
        old_topic: topic2,
        new_topic: topic3,
    });

    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "3,2");
    assert.equal(rs.get_topic_recent_senders(stream3, topic2).toString(), "3");

    // Test stream change
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "3,2");
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "");

    message7.stream_id = stream4;
    message8.stream_id = stream4;
    rs.process_topic_edit({
        message_ids: [message7.id, message8.id],
        old_stream_id: stream3,
        new_stream_id: stream4,
        old_topic: topic3,
        new_topic: topic3,
    });

    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "3,2");

    // Test stream & topic change
    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "3,2");
    assert.equal(rs.get_topic_recent_senders(stream5, topic4).toString(), "");

    message7.stream_id = stream5;
    message7.topic = topic4;

    message8.stream_id = stream5;
    message8.topic = topic4;

    rs.process_topic_edit({
        message_ids: [message7.id, message8.id],
        old_stream_id: stream4,
        new_stream_id: stream5,
        old_topic: topic3,
        new_topic: topic4,
    });

    assert.equal(rs.get_topic_recent_senders(stream4, topic3).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream5, topic4).toString(), "3,2");
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "1,2");

    // delete message1 and message5 sent by sender1
    rs.update_topics_of_deleted_message_ids([message1.id, message5.id]);
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "2");

    // test that we can remove again, harmlessly
    rs.update_topics_of_deleted_message_ids([message1.id, message5.id]);
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "2");

    // remove some more senders
    rs.update_topics_of_deleted_message_ids([message2.id, message3.id, message4.id, message5.id]);
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "");

    rs.update_topics_of_deleted_message_ids([message6.id, message7.id, message8.id, message9.id]);
    assert.equal(rs.get_topic_recent_senders(stream1, topic1).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream2, topic2).toString(), "");
    assert.equal(rs.get_topic_recent_senders(stream3, topic3).toString(), "");

    // deleting an old message which isn't locally stored.
    // We are just testing that it doesn't raise an error;
    // no changes should take place in this case.
    rs.update_topics_of_deleted_message_ids([-1]);

    // Comparing on a non-existent topic doesn't crash.
    assert.equal(
        rs.compare_by_recency({user_id: sender2}, {user_id: sender1}, stream3, "bogus") < 0,
        true,
    );
});

test("process_pms", () => {
    const sender1 = 1; // Current user id
    const sender2 = 2;
    const sender3 = 3;

    const user_ids_string = "2,3,4";
    rs.process_private_message({
        to_user_ids: user_ids_string,
        sender_id: sender2,
        id: 1,
    });
    rs.process_private_message({
        to_user_ids: user_ids_string,
        sender_id: sender3,
        id: 2,
    });
    rs.process_private_message({
        to_user_ids: user_ids_string,
        sender_id: sender1,
        id: 3,
    });

    // Recent topics displays avatars in the opposite order to this since
    // that was simpler to implement in HTML.
    assert.deepEqual(rs.get_pm_recent_senders(user_ids_string), {
        participants: [1, 3, 2],
        non_participants: [4],
    });
    // PM doesn't exist.
    assert.deepEqual(rs.get_pm_recent_senders("1000,2000"), {
        participants: [],
        non_participants: [],
    });

    rs.process_private_message({
        to_user_ids: "1",
        sender_id: sender1,
        id: 4,
    });
    assert.deepEqual(rs.get_pm_recent_senders("1"), {
        participants: [1],
        non_participants: [],
    });
});
