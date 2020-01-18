set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

set_global('narrow_state', {});
set_global('unread', {});
set_global('muting', {});
set_global('stream_popover', {});
set_global('message_list', {});

zrequire('hash_util');
zrequire('stream_data');
zrequire('unread');
zrequire('topic_data');
zrequire('topic_list');

const devel = {
    stream_id: 555,
    name: 'devel',
};

const general = {
    stream_id: 556,
    name: 'general',
};

stream_data.add_sub('devel', devel);
stream_data.add_sub('general', general);

function clear() {
    narrow_state.topic = () => undefined;
    topic_data.reset();
    stream_popover.hide_topic_popover = function () {};
    muting.is_topic_muted = () => false;
}

function get_list_info() {
    const stream_id = general.stream_id;
    const widget = topic_list.widget(undefined, stream_id);
    return widget.get_list_info();
}

run_test('get_list_info w/real topic_data', () => {
    clear();

    const empty_list_info = get_list_info();

    assert.deepEqual(empty_list_info, {
        items: [],
        more_topics_unreads: 0,
        num_possible_topics: 0,
    });

    _.each(_.range(7), (i) => {
        const topic_name = 'topic ' + i;
        topic_data.add_message({
            stream_id: general.stream_id,
            topic_name: topic_name,
            message_id: 1000 + i,
        });
    });

    const list_info = get_list_info();
    assert.equal(list_info.items.length, 5);
    assert.equal(list_info.more_topics_unreads, 0);
    assert.equal(list_info.num_possible_topics, 7);

    assert.deepEqual(list_info.items[0], {
        is_active_topic: false,
        is_muted: false,
        is_zero: true,
        topic_name: 'topic 6',
        unread: 0,
        url: '#narrow/stream/556-general/topic/topic.206',
    });
});

run_test('get_list_info unreads', () => {
    clear();

    let list_info;

    // Going forward, we just stub get_recent_names
    // for simpler test setup.
    topic_data.get_recent_names = () => {
        return _.map(_.range(15), (i) => {
            return 'topic ' + i;
        });
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
        _.map(list_info.items, (li) => li.topic_name),
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
        _.map(list_info.items, (li) => li.topic_name),
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
});

run_test('topic_list_build_widget', () => {
    clear();

    topic_data.get_recent_names = () => {
        return ['coding'];
    };

    narrow_state.topic = function () {
        return 'testing';
    };

    unread.num_unread_for_topic = function () {
        return 3;
    };

    let checked_mutes;
    let rendered;

    global.stub_templates(function (name, info) {
        assert.equal(name, 'topic_list_item');
        const expected = {
            topic_name: 'coding',
            unread: 3,
            is_zero: false,
            is_muted: false,
            is_active_topic: false,
            url: '#narrow/stream/555-devel/topic/coding',
        };
        assert.deepEqual(info, expected);
        rendered = true;
        return '<topic list item>';
    });

    muting.is_topic_muted = function (stream_id, topic_name) {
        assert.equal(stream_id, devel.stream_id);
        assert.equal(topic_name, 'coding');
        checked_mutes = true;
        return false;
    };

    const ul = $('<ul class="topic-list">');

    const list_items = [];

    ul.append = function (item) {
        list_items.push(item);
    };

    const parent_elem = $.create('parent_elem');
    let attached_to_parent;

    parent_elem.append = function (child) {
        assert.equal(child, ul);
        attached_to_parent = true;
    };

    assert.equal(topic_list.active_stream_id(), undefined);

    const widget = topic_list.widget(parent_elem, devel.stream_id);

    widget.build_more_topics_section = function () {
        return $('<more topics>');
    };

    widget.build();

    assert(widget.get_stream_id(), devel.stream_id);
    assert.equal(widget.get_parent(), parent_elem);

    assert(checked_mutes);
    assert(rendered);
    assert.equal(list_items[0].html(), '<topic list item>');
    assert.equal(list_items[1].html(), '<more topics>');
    assert(attached_to_parent);

});
