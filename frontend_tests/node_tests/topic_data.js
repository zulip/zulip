set_global('i18n', global.stub_i18n);

zrequire('unread');
zrequire('util');
zrequire('stream_data');
zrequire('topic_data');

set_global('channel', {});
set_global('message_list', {});

run_test('basics', () => {
    const stream_id = 55;

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 101,
        topic_name: 'toPic1',
    });

    let history = topic_data.get_recent_names(stream_id);
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
});

run_test('is_complete_for_stream_id', () => {
    const sub = {
        name: 'devel',
        stream_id: 444,
        first_message_id: 1000,
    };
    stream_data.add_sub(sub.name, sub);

    message_list.all = {
        empty: () => false,
        fetch_status: {
            has_found_newest: () => true,
        },
        first: () => {
            return {id: 5};
        },
    };

    assert.equal(
        topic_data.is_complete_for_stream_id(sub.stream_id),
        true);


    // Now simulate a more recent message id.
    message_list.all.first = () => {
        return {id: sub.first_message_id + 1};
    };

    // Note that we'll return `true` here due to
    // fetched_stream_ids having the stream_id now.
    assert.equal(
        topic_data.is_complete_for_stream_id(sub.stream_id),
        true);

    // But now clear the data to see what we'd have without
    // the previous call.
    topic_data.reset();

    assert.equal(
        topic_data.is_complete_for_stream_id(sub.stream_id),
        false);
});

run_test('server_history', () => {
    const sub = {
        name: 'devel',
        stream_id: 66,
    };
    const stream_id = sub.stream_id;
    stream_data.add_sub(sub.name, sub);

    message_list.all.fetch_status.has_found_newest = () => false;

    assert.equal(
        topic_data.is_complete_for_stream_id(stream_id),
        false);

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 501,
        topic_name: 'local',
    });

    function add_server_history() {
        topic_data.add_history(stream_id, [
            { name: 'local', max_id: 501 },
            { name: 'hist2', max_id: 31 },
            { name: 'hist1', max_id: 30 },
        ]);
    }

    add_server_history();

    // Since we added history, now subsequent calls
    // to is_complete_for_stream_id will return true.
    assert.equal(
        topic_data.is_complete_for_stream_id(stream_id),
        true);

    let history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['local', 'hist2', 'hist1']);

    // If new activity comes in for historical messages,
    // they can bump to the front of the list.
    topic_data.add_message({
        stream_id: stream_id,
        message_id: 502,
        topic_name: 'hist1',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['hist1', 'local', 'hist2']);

    // server history is allowed to backdate hist1
    add_server_history();
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['local', 'hist2', 'hist1']);

    // Removing a local message removes the topic if we have
    // our counts right.
    topic_data.remove_message({
        stream_id: stream_id,
        topic_name: 'local',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['hist2', 'hist1']);

    // We can try to remove a historical message, but it should
    // have no effect.
    topic_data.remove_message({
        stream_id: stream_id,
        topic_name: 'hist2',
    });
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['hist2', 'hist1']);

    // If we call back to the server for history, the
    // effect is always additive.  We may decide to prune old
    // topics in the future, if they dropped off due to renames,
    // but that is probably an edge case we can ignore for now.
    topic_data.add_history(stream_id, [
        { name: 'hist2', max_id: 931 },
        { name: 'hist3', max_id: 5 },
    ]);
    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['hist2', 'hist1', 'hist3']);
});

run_test('test_unread_logic', () => {
    const stream_id = 77;

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 201,
        topic_name: 'toPic1',
    });

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 45,
        topic_name: 'topic2',
    });

    let history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['toPic1', 'topic2']);

    const msgs = [
        { id: 150, topic: 'TOPIC2' }, // will be ignored
        { id: 61, topic: 'unread1' },
        { id: 60, topic: 'unread1' },
        { id: 20, topic: 'UNREAD2' },
    ];

    _.each(msgs, (msg) => {
        msg.type = 'stream';
        msg.stream_id = stream_id;
        msg.unread = true;
    });

    unread.process_loaded_messages(msgs);

    history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['toPic1', 'unread1', 'topic2', 'UNREAD2']);
});

run_test('test_stream_has_topics', () => {
    const stream_id = 88;

    assert.equal(topic_data.stream_has_topics(stream_id), false);

    topic_data.find_or_create(stream_id);

    // This was a bug before--just creating a bucket does not
    // mean we have actual topics.
    assert.equal(topic_data.stream_has_topics(stream_id), false);

    topic_data.add_message({
        stream_id: stream_id,
        message_id: 888,
        topic_name: 'whatever',
    });

    assert.equal(topic_data.stream_has_topics(stream_id), true);
});

run_test('server_history_end_to_end', () => {
    topic_data.reset();

    const stream_id = 99;

    const topics = [
        { name: 'topic3', max_id: 501 },
        { name: 'topic2', max_id: 31 },
        { name: 'topic1', max_id: 30 },
    ];

    let get_success_callback;
    let on_success_called;

    channel.get = function (opts) {
        assert.equal(opts.url, '/json/users/me/99/topics');
        assert.deepEqual(opts.data, {});
        get_success_callback = opts.success;
    };

    topic_data.get_server_history(stream_id, () => {
        on_success_called = true;
    });

    get_success_callback({topics: topics});

    assert(on_success_called);

    const history = topic_data.get_recent_names(stream_id);
    assert.deepEqual(history, ['topic3', 'topic2', 'topic1']);

    // Try getting server history for a second time.

    channel.get = () => {
        throw Error('We should not get more data.');
    };

    on_success_called = false;
    topic_data.get_server_history(stream_id, () => {
        on_success_called = true;
    });
    assert(on_success_called);

});
