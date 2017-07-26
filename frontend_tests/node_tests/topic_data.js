var topic_data = require('js/topic_data.js');

(function test_basics() {
    var stream_id = 55;

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 101,
        topic_name: 'toPic1',
    });

    var history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['toPic1']);

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 102,
        topic_name: 'Topic1',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['Topic1']);

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 103,
        topic_name: 'topic2',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['topic2', 'Topic1']);

    // Removing first topic1 message has no effect.
    topic_data.remove_message({
        stream_id: stream_id,
        topic_name: 'toPic1',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['topic2', 'Topic1']);

    // Removing second topic1 message removes the topic.
    topic_data.remove_message({
        stream_id: stream_id,
        topic_name: 'Topic1',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['topic2']);

    // Test that duplicate remove does not crash us.
    topic_data.remove_message({
        stream_id: stream_id,
        topic_name: 'Topic1',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['topic2']);

    // get to 100% coverage for defensive code
    topic_data.remove_message({
        stream_id: 9999999,
    });
}());

