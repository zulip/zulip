set_global('narrow_state', {});
set_global('unread', {});
set_global('muting', {});
set_global('message_list', {});
set_global('i18n', global.stub_i18n);

zrequire('hash_util');
zrequire('stream_data');
zrequire('unread');
zrequire('topic_data');
const topic_list_data = zrequire('topic_list_data');

const general = {
    stream_id: 556,
    name: 'general',
};

stream_data.add_sub(general);

function clear() {
    narrow_state.topic = () => undefined;
    topic_data.reset();
    muting.is_topic_muted = () => false;
}

function get_list_info(zoomed) {
    const stream_id = general.stream_id;
    return topic_list_data.get_list_info(
        stream_id, zoomed);
}

run_test('get_list_info w/real topic_data', () => {
    clear();

    let list_info;
    const empty_list_info = get_list_info();

    assert.deepEqual(empty_list_info, {
        items: [],
        more_topics_unreads: 0,
        num_possible_topics: 0,
    });

    for (const i of _.range(7)) {
        const topic_name = 'topic ' + i;
        topic_data.add_message({
            stream_id: general.stream_id,
            topic_name: topic_name,
            message_id: 1000 + i,
        });
    }

    narrow_state.topic = () => 'topic 6';

    list_info = get_list_info();
    assert.equal(list_info.items.length, 5);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 7);

    assert.deepEqual(list_info.items[0], {
        is_active_topic: true,
        is_muted: false,
        is_zero: true,
        topic_name: 'topic 6',
        unread: 0,
        url: '#narrow/stream/556-general/topic/topic.206',
    });

    // If we zoom in, we'll show all 7 topics.
    const zoomed = true;
    list_info = get_list_info(zoomed);
    assert.equal(list_info.items.length, 7);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 7);
});

run_test('get_list_info unreads', () => {
    clear();

    let list_info;

    // Going forward, we just stub get_recent_names
    // for simpler test setup.
    topic_data.get_recent_names = () => {
        return _.range(15).map(i => 'topic ' + i);
    };

    const unread_cnt = {};
    unread.num_unread_for_topic = (stream_id, topic_name) => {
        assert.equal(stream_id, general.stream_id);
        return unread_cnt[topic_name] || 0;
    };

    /*
        We have 15 topics, but we only show up
        to 8 topics, depending on how many have
        unread counts.  We only show a max of 5
        fully-read topics.

        So first we'll get 7 topics, where 2 are
        unread.
    */
    unread_cnt['topic 8'] = 8;
    unread_cnt['topic 9'] = 9;

    list_info = get_list_info();
    assert.equal(list_info.items.length, 7);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 15);

    assert.deepEqual(
        list_info.items.map(li => li.topic_name),
        [
            'topic 0',
            'topic 1',
            'topic 2',
            'topic 3',
            'topic 4',
            'topic 8',
            'topic 9',
        ]);

    unread_cnt['topic 6'] = 6;
    unread_cnt['topic 7'] = 7;

    list_info = get_list_info();
    assert.equal(list_info.items.length, 8);
    assert.equal(list_info.more_topics_unreads, 9);
    assert.equal(list_info.num_possible_topics, 15);

    assert.deepEqual(
        list_info.items.map(li => li.topic_name),
        [
            'topic 0',
            'topic 1',
            'topic 2',
            'topic 3',
            'topic 4',
            'topic 6',
            'topic 7',
            'topic 8',
        ]);

    unread_cnt['topic 4'] = 4;
    unread_cnt['topic 5'] = 5;
    unread_cnt['topic 13'] = 13;

    muting.is_topic_muted = (stream_id, topic_name) => {
        assert.equal(stream_id, general.stream_id);
        return topic_name === 'topic 4';
    };

    list_info = get_list_info();
    assert.equal(list_info.items.length, 8);
    assert.equal(list_info.more_topics_unreads, 9 + 13);
    assert.equal(list_info.num_possible_topics, 15);

    assert.deepEqual(
        list_info.items.map(li => li.topic_name),
        [
            'topic 0',
            'topic 1',
            'topic 2',
            'topic 3',
            'topic 5',
            'topic 6',
            'topic 7',
            'topic 8',
        ]);
});
