const rt = zrequire('recent_topics');

const people = {
    is_my_user_id: function (id) {
        return id === 1;
    },
};

set_global('people', people);

// Custom Data

// New stream
const stream1 = 1;

// Topics in the stream
const topic1 = "topic-1";  // No Other sender
const topic2 = "topic-2";  // Other sender
const topic3 = "topic-3";  // User not present
const topic4 = "topic-4";  // User not present
const topic5 = "topic-5";  // other sender
const topic6 = "topic-6";  // other sender

const topic7 = "topic-7";  // muted topic
set_global('muting', {
    get_muted_topics: () => {
        return [
            (stream1, topic7),
        ];
    },
});

// sender1 == current user
// sender2 == any other user
const sender1 = 1;
const sender2 = 2;

const messages = [];

messages[0] = {
    stream_id: stream1,
    timestamp: 1000,
    topic: topic1,
    sender_id: sender1,
    type: 'stream',
};

messages[1] = {
    stream_id: stream1,
    timestamp: 1010,
    topic: topic2,
    sender_id: sender1,
    type: 'stream',
};

messages[2] = {
    stream_id: stream1,
    timestamp: messages[1].timestamp + 1,
    topic: topic2,
    sender_id: sender2,
    type: 'stream',
};

messages[3] = {
    stream_id: stream1,
    timestamp: 1020,
    topic: topic3,
    sender_id: sender2,
    type: 'stream',
};

messages[4] = {
    stream_id: stream1,
    timestamp: 1030,
    topic: topic4,
    sender_id: sender2,
    type: 'stream',
};

messages[5] = {
    stream_id: stream1,
    timestamp: 1040,
    topic: topic5,
    sender_id: sender1,
    type: 'stream',
};

messages[6] = {
    stream_id: stream1,
    timestamp: messages[5].timestamp + 1,
    topic: topic5,
    sender_id: sender2,
    type: 'stream',
};

messages[7] = {
    stream_id: stream1,
    timestamp: 1050,
    topic: topic6,
    sender_id: sender1,
    type: 'stream',
};

messages[8] = {
    stream_id: stream1,
    timestamp: messages[7].timestamp + 1,
    topic: topic6,
    sender_id: sender2,
    type: 'stream',
};

messages[9] = {
    stream_id: stream1,
    timestamp: 1060,
    topic: topic7,
    sender_id: sender1,
    type: 'stream',
};

run_test('basic assertions', () => {

    rt.process_messages(messages);
    let all_topics = rt.get();

    // Check for expected lengths.
    assert(all_topics.size, 4); // Participated in 4 topics.

    // Last message was sent by us.
    assert(all_topics.has(stream1 + ':' + topic1));

    // Last message was sent by them.
    assert(all_topics.has(stream1 + ':' + topic2));

    // No message was sent by us.
    assert(!all_topics.has(stream1 + ':' + topic3));
    assert(!all_topics.has(stream1 + ':' + topic4));

    // Last message was sent by them.
    assert(all_topics.has(stream1 + ':' + topic5));
    assert(all_topics.has(stream1 + ':' + topic6));

    // Send new message to topic1
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[1].timestamp + 1,
        topic: topic1,
        sender_id: sender1,
        type: 'stream',
    });

    // Send new message to topic5
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[6].timestamp + 2,
        topic: topic5,
        sender_id: sender2,
        type: 'stream',
    });

    // Send new message to topic6
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[8].timestamp + 1,
        topic: topic6,
        sender_id: sender2,
        type: 'stream',
    });

    // Send new message to topic7 (muted)
    rt.process_message({
        stream_id: stream1,
        timestamp: messages[8].timestamp + 1,
        topic: topic7,
        sender_id: sender1,
        type: 'stream',
    });

    all_topics = rt.get();

    // Check for expected lengths.
    assert(all_topics.size, 4); // Participated in 4 topics.
    assert(all_topics.has(stream1 + ':' + topic1));
    assert(all_topics.has(stream1 + ':' + topic5));
    assert(all_topics.has(stream1 + ':' + topic6));

});
