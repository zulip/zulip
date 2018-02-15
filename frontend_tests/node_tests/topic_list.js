set_global('$', global.make_zjquery());
set_global('i18n', global.stub_i18n);

set_global('narrow_state', {});
set_global('stream_data', {});
set_global('unread', {});
set_global('muting', {});
set_global('stream_popover', {});
set_global('templates', {});

zrequire('hash_util');
zrequire('narrow');
zrequire('stream_data');
zrequire('topic_data');
zrequire('topic_list');

(function test_topic_list_build_widget() {
    var stream_id = 555;

    topic_data.reset();
    topic_data.add_message({
        stream_id: stream_id,
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

    stream_data.get_sub_by_id = function (stream_id) {
        assert.equal(stream_id, 555);
        return {
            name: 'devel',
        };
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
            url: '#narrow/stream/devel/subject/coding',
        };
        assert.deepEqual(info, expected);
        rendered = true;
        return '<topic list item>';
    };

    muting.is_topic_muted = function (stream_name, topic_name) {
        assert.equal(stream_name, 'devel');
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

    var widget = topic_list.widget(parent_elem, stream_id);

    widget.build_more_topics_section = function () {
        return $('<more topics>');
    };

    widget.build();

    assert(widget.is_for_stream(stream_id));
    assert.equal(widget.get_parent(), parent_elem);

    assert(checked_mutes);
    assert(rendered);
    assert.equal(list_items[0].html(), '<topic list item>');
    assert.equal(list_items[1].html(), '<more topics>');
    assert(attached_to_parent);

}());
