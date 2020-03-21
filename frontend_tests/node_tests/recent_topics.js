const rt = zrequire('recent_topics');
set_global('people', {
    is_my_user_id: function (id) {
        return id === 1;
    },
});

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
    is_topic_muted: (stream_id, topic) => {
        if (stream_id === stream1 && topic === topic7) {
            return true;
        }
        return false;
    },
});

// sender1 == current user
// sender2 == any other user
const sender1 = 1;
const sender2 = 2;

const messages = [];

let id = 0;

messages[0] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic1,
    sender_id: sender1,
    type: 'stream',
};

messages[1] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic2,
    sender_id: sender1,
    type: 'stream',
};

messages[2] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic2,
    sender_id: sender2,
    type: 'stream',
    starred: true,
};

messages[3] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic3,
    sender_id: sender2,
    type: 'stream',
};

messages[4] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic4,
    sender_id: sender2,
    type: 'stream',
    starred: true,
};

messages[5] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic5,
    sender_id: sender1,
    type: 'stream',
};

messages[6] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic5,
    sender_id: sender2,
    type: 'stream',
};

messages[7] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic6,
    sender_id: sender1,
    type: 'stream',
};

messages[8] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic6,
    sender_id: sender2,
    type: 'stream',
};

messages[9] = {
    stream_id: stream1,
    id: id += 1,
    topic: topic7,
    sender_id: sender1,
    type: 'stream',
};

function verify_topic_data(all_topics, stream, topic, last_msg_id,
                           participated, starred_count, is_muted) {
    // default is_muted to false since most of the test cases will
    // be not muted
    is_muted = is_muted || false;
    const topic_data = all_topics.get(stream + ':' + topic);
    assert.equal(topic_data.last_msg_id, last_msg_id);
    assert.equal(topic_data.participated, participated);
    assert.equal(topic_data.starred.size, starred_count);
    assert.equal(topic_data.muted, is_muted);
}

run_test('basic assertions', () => {

    rt.process_messages(messages);
    let all_topics = rt.get();

    // Check for expected lengths.
    // total 7 topics, 1 muted
    assert.equal(all_topics.size, 7);
    assert.equal(Array.from(all_topics.keys()).toString(),
                 '1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1');

    rt.process_message({
        type: 'private',
    });

    // Private msgs are not processed.
    assert.equal(all_topics.size, 7);
    assert.equal(Array.from(all_topics.keys()).toString(),
                 '1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1');

    // participated but not starred
    verify_topic_data(all_topics, stream1, topic1, messages[0].id, true, 0);

    // starred and participated
    verify_topic_data(all_topics, stream1, topic2, messages[2].id, true, 1);

    // No message was sent by us.
    verify_topic_data(all_topics, stream1, topic3, messages[3].id, false, 0);

    // Not participated but starred
    verify_topic_data(all_topics, stream1, topic4, messages[4].id, false, 1);

    // topic1 now starred
    rt.process_message({
        stream_id: stream1,
        id: id += 1,
        topic: topic1,
        sender_id: sender1,
        type: 'stream',
        starred: true,
    });

    all_topics = rt.get();

    assert.equal(Array.from(all_topics.keys()).toString(),
                 '1:topic-1,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2');

    verify_topic_data(all_topics, stream1, topic1, id, true, 1);

    // topic3 now participated
    rt.process_message({
        stream_id: stream1,
        id: id += 1,
        topic: topic3,
        sender_id: sender1,
        type: 'stream',
    });

    all_topics = rt.get();
    assert.equal(Array.from(all_topics.keys()).toString(),
                 '1:topic-3,1:topic-1,1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-2');
    verify_topic_data(all_topics, stream1, topic3, id, true, 0);

    // Send new message to topic7 (muted)
    rt.process_message({
        stream_id: stream1,
        id: id += 1,
        topic: topic7,
        sender_id: sender1,
        type: 'stream',
    });

    all_topics = rt.get();
    assert.equal(Array.from(all_topics.keys()).toString(),
                 '1:topic-7,1:topic-3,1:topic-1,1:topic-6,1:topic-5,1:topic-4,1:topic-2');
    verify_topic_data(all_topics, stream1, topic7, id, true, 0, true);
});
