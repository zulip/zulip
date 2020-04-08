let rt = zrequire('recent_topics');
zrequire('message_util');

set_global('$', global.make_zjquery());
set_global('hashchange', {
    exit_overlay: () => {},
});
set_global('overlays', {
    open_overlay: (opts) => {
        overlays.close_callback = opts.on_close;
    },
});
set_global('people', {
    is_my_user_id: function (id) {
        return id === 1;
    },
});

// Custom Data

// New stream
const stream1 = 1;
const stream2 = 2;
const stream3 = 3;

// Topics in the stream
const topic1 = "topic-1";  // No Other sender
const topic2 = "topic-2";  // Other sender
const topic3 = "topic-3";  // User not present
const topic4 = "topic-4";  // User not present
const topic5 = "topic-5";  // other sender
const topic6 = "topic-6";  // other sender
const topic7 = "topic-7";  // muted topic
const topic8 = "topic-8";
const topic9 = "topic-9";

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

set_global('message_list', {
    all: {
        all_messages: function () {
            return messages;
        },
    },
});

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

    // unmute topic7
    rt.update_topic_is_muted(stream1, topic7, false);
    all_topics = rt.get();
    verify_topic_data(all_topics, stream1, topic7, id, true, 0, false);

    // mute topic7
    rt.update_topic_is_muted(stream1, topic7, true);
    all_topics = rt.get();
    verify_topic_data(all_topics, stream1, topic7, id, true, 0, true);

    // a topic gets muted which we are not tracking
    assert.equal(rt.update_topic_is_muted(stream1, "topic-10", true), false);
});

run_test('test_topic_edit', () => {
    rt = zrequire('recent_topics');
    rt.process_messages(messages);

    let all_topics = rt.get();
    assert.equal(Array.from(all_topics.keys()).toString(),
                 '1:topic-7,1:topic-6,1:topic-5,1:topic-4,1:topic-3,1:topic-2,1:topic-1');

    ////////////////// test change topic //////////////////
    verify_topic_data(all_topics, stream1, topic6, messages[8].id, true, 0);
    assert.equal(all_topics.get(stream1 + ":" + topic8), undefined);

    // change topic of topic6 to topic8
    messages[7].topic = topic8;
    messages[8].topic = topic8;
    rt.process_topic_edit(stream1, topic6, topic8);
    all_topics = rt.get();

    verify_topic_data(all_topics, stream1, topic8, messages[8].id, true, 0);
    assert.equal(all_topics.get(stream1 + ":" + topic6), undefined);

    ////////////////// test change topic to muted topic //////////////////
    verify_topic_data(all_topics, stream1, topic8, messages[8].id, true, 0);
    verify_topic_data(all_topics, stream1, topic7, messages[9].id, true, 0, true);

    // change topic of topic8 to topic7
    messages[7].topic = topic7;
    messages[8].topic = topic7;
    rt.process_topic_edit(stream1, topic8, topic7);
    all_topics = rt.get();

    assert.equal(all_topics.get(stream1 + ":" + topic8), undefined);
    verify_topic_data(all_topics, stream1, topic7, messages[9].id, true, 0, true);

    ////////////////// test stream change //////////////////
    verify_topic_data(all_topics, stream1, topic1, messages[0].id, true, 0);
    assert.equal(all_topics.get(stream2 + ":" + topic1), undefined);

    messages[0].stream_id = stream2;
    rt.process_topic_edit(stream1, topic1, topic1, stream2);
    all_topics = rt.get();

    assert.equal(all_topics.get(stream1 + ":" + topic1), undefined);
    verify_topic_data(all_topics, stream2, topic1, messages[0].id, true, 0);

    ////////////////// test stream & topic change //////////////////
    verify_topic_data(all_topics, stream2, topic1, messages[0].id, true, 0);
    assert.equal(all_topics.get(stream3 + ":" + topic9), undefined);

    messages[0].stream_id = stream3;
    messages[0].topic = topic9;
    rt.process_topic_edit(stream2, topic1, topic9, stream3);
    all_topics = rt.get();

    assert.equal(all_topics.get(stream2 + ":" + topic1), undefined);
    verify_topic_data(all_topics, stream3, topic9, messages[0].id, true, 0);
});

run_test("test_recent_topics_launch", () => {

    global.stub_templates(function (template_name) {
        assert.equal(template_name, 'recent_topics_table');
        return '<recent_topics table stub>';
    });
    rt.launch();
    overlays.close_callback();
});
