set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

set_global('narrow_state', {});
set_global('unread', {});
set_global('muting', {});
set_global('stream_popover', {});
set_global('templates', {});

zrequire('hash_util');
zrequire('stream_data');
zrequire('unread');
zrequire('topic_data');
zrequire('topic_list');

var devel = {
    stream_id: 555,
    name: 'devel',
};

stream_data.add_sub('devel', devel);

run_test('topic_list_build_widget', () => {

    topic_data.reset();
    topic_data.add_message({
        stream_id: devel.stream_id,
        topic_name: 'coding',
        message_id: 400,
    });

    stream_popover.hide_topic_popover = function () {};

    narrow_state.topic = function () {
        return 'testing';
    };

    unread.num_unread_for_topic = function () {
        return 3;
    };

    var checked_mutes;
    var rendered;

    templates.render = function (name, info) {
        assert.equal(name, 'topic_list_item');
        var expected = {
            topic_name: 'coding',
            unread: 3,
            is_zero: false,
            is_muted: false,
            url: '#narrow/stream/555-devel/topic/coding',
        };
        assert.deepEqual(info, expected);
        rendered = true;
        return '<topic list item>';
    };

    muting.is_topic_muted = function (stream_id, topic_name) {
        assert.equal(stream_id, devel.stream_id);
        assert.equal(topic_name, 'coding');
        checked_mutes = true;
        return false;
    };

    var ul = $('<ul class="topic-list">');

    var list_items = [];

    ul.append = function (item) {
        list_items.push(item);
    };

    var parent_elem = $.create('parent_elem');
    var attached_to_parent;

    parent_elem.append = function (child) {
        assert.equal(child, ul);
        attached_to_parent = true;
    };

    assert.equal(topic_list.active_stream_id(), undefined);

    var widget = topic_list.widget(parent_elem, devel.stream_id);

    widget.build_more_topics_section = function () {
        return $('<more topics>');
    };

    widget.build();

    assert(widget.is_for_stream(devel.stream_id));
    assert.equal(widget.get_parent(), parent_elem);

    assert(checked_mutes);
    assert(rendered);
    assert.equal(list_items[0].html(), '<topic list item>');
    assert.equal(list_items[1].html(), '<more topics>');
    assert(attached_to_parent);

});
