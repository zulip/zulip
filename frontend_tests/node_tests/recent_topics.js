var rt = zrequire('recent_topics');

var people = {
    is_my_user_id: function (id) {
        return id === 1;
    },
};

set_global('people', people);

run_test('basic assertions',() => {
    var stream1 = 1;

    var topic1 = "topic-1";
    var topic2 = "topic-2";
    var topic3 = "topic-3";
    var topic4 = "topic-4";
    var topic5 = "topic-5";
    var topic6 = "topic-6";

    var sender1 = 1;
    var sender2 = 2;

    // New stream
    var messages = [];
    messages[0] = {
        stream_id: stream1,
        timestamp: 1000,
        subject: topic1,
        sender_id: sender1,
        unread: false,
        type: 'stream',
    };

    messages[1] = {
        stream_id: stream1,
        timestamp: 1010,
        subject: topic2,
        sender_id: sender1,
        unread: false,
        type: 'stream',
    };
    messages[2] = {
        stream_id: stream1,
        timestamp: messages[1].timestamp + 1,
        subject: topic2,
        sender_id: sender2,
        unread: false,
        type: 'stream',
    };

    messages[3] = {
        stream_id: stream1,
        timestamp: 1020,
        subject: topic3,
        sender_id: sender2,
        unread: true,
        type: 'stream',
    };

    messages[4] = {
        stream_id: stream1,
        timestamp: 1030,
        subject: topic4,
        sender_id: sender1,
        unread: false,
        type: 'stream',
    };
    messages[5] = {
        stream_id: stream1,
        timestamp: messages[4].timestamp + 1,
        subject: topic4,
        sender_id: sender2,
        unread: true,
        type: 'stream',
    };

    messages[6] = {
        stream_id: stream1,
        timestamp: 1040,
        subject: topic5,
        sender_id: sender1,
        unread: false,
        type: 'stream',
    };
    messages[7] = {
        stream_id: stream1,
        timestamp: messages[6].timestamp + 1,
        subject: topic5,
        sender_id: sender2,
        unread: true,
        type: 'stream',
    };

    messages[8] = {
        stream_id: stream1,
        timestamp: 1050,
        subject: topic6,
        sender_id: sender1,
        unread: false,
        type: 'stream',
    };
    messages[9] = {
        stream_id: stream1,
        timestamp: 1060,
        subject: topic6,
        sender_id: sender2,
        unread: true,
        type: 'stream',
    };

    rt.process_messages(messages);
    var all_topics = rt.get();
    var rel_topics = rt.get_relevant();

    // Check for expected lengths.
    assert(all_topics.num_items, 6); // Participated in 4 topics.
    assert(rel_topics.num_items, 2); // Two unread topics.

    // Last message was sent by us.
    assert(all_topics.has(stream1 + ':' + topic1));
    assert(!rel_topics.has(stream1 + ':' + topic1));
    assert(all_topics.get(stream1 + ':' + topic1).read);

    // Last message was sent by them but we've read it.
    assert(all_topics.has(stream1 + ':' + topic2));
    assert(!rel_topics.has(stream1 + ':' + topic2));
    assert(all_topics.get(stream1 + ':' + topic2).read);

    // No message was sent by us.
    assert(!all_topics.has(stream1 + ':' + topic3));
    assert(!rel_topics.has(stream1 + ':' + topic3));

    // Last message was sent by them and is unread.
    assert(all_topics.has(stream1 + ':' + topic4));
    assert(rel_topics.has(stream1 + ':' + topic4));
    assert(!all_topics.get(stream1 + ':' + topic4).read);

    // Last message was sent by them and is unread.
    assert(all_topics.has(stream1 + ':' + topic5));
    assert(rel_topics.has(stream1 + ':' + topic5));
    assert(!all_topics.get(stream1 + ':' + topic5).read);

    // Last message was sent by them and is unread.
    assert(all_topics.has(stream1 + ':' + topic6));
    assert(rel_topics.has(stream1 + ':' + topic6));
    assert(!all_topics.get(stream1 + ':' + topic6).read);

    // Send new message to topic1 and mark it as unread.
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[1].timestamp + 1,
        subject: topic1,
        sender_id: sender2,
        unread: true,
        type: 'stream',
    });

    // Mark last message to topic4 as read.
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[5].timestamp,
        subject: topic4,
        sender_id: sender2,
        unread: false,
        type: 'stream',
    });

    // Send new message to topic5, and mark it as unread.
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[7].timestamp + 2,
        subject: topic5,
        sender_id: sender2,
        unread: true,
        type: 'stream',
    });

    // Send new message to topic6 and mark it as read.
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[9].timestamp + 1,
        subject: topic6,
        sender_id: sender2,
        unread: false,
        type: 'stream',
    });

    all_topics = rt.get();
    rel_topics = rt.get_relevant();

    // Check for expected lengths.
    assert(all_topics.num_items, 6); // Participated in 4 topics.
    assert(rel_topics.num_items, 3); // Three unread topics.

    // Last message was sent by them and is unread.
    assert(all_topics.has(stream1 + ':' + topic1));
    assert(rel_topics.has(stream1 + ':' + topic1));
    assert(!all_topics.get(stream1 + ':' + topic1).read);

    // Last message was sent by them and is unread.
    assert(all_topics.has(stream1 + ':' + topic5));
    assert(rel_topics.has(stream1 + ':' + topic5));
    assert(!all_topics.get(stream1 + ':' + topic5).read);

    // Last message was sent by them but we've read it.
    assert(all_topics.has(stream1 + ':' + topic6));
    assert(!rel_topics.has(stream1 + ':' + topic6));
    assert(all_topics.get(stream1 + ':' + topic6).read);

});
