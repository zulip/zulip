set_global('$', global.make_zjquery());

set_global('stream_data', {});
set_global('unread', {});
set_global('muting', {});
set_global('templates', {});

zrequire('hash_util');
zrequire('narrow');
zrequire('topic_data');
zrequire('topic_list');

(function test_topic_list_build_widget() {
    var stream_id = 555;
    var active_topic = "testing";
    var max_topics = 5;

    topic_data.reset();
    topic_data.add_message({
        stream_id: stream_id,
        topic_name: 'coding',
        message_id: 400,
    });

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

    var item_appended;

    ul.append = function (item) {
        assert.equal(item.html(), '<topic list item>');
        item_appended = true;
    };

    var parent_elem = $.create('parent_elem');
    var attached_to_parent;

    parent_elem.append = function (child) {
        assert.equal(child, ul);
        attached_to_parent = true;
    };

    assert.equal(topic_list.active_stream_id(), undefined);

    var widget = topic_list.build_widget(parent_elem, stream_id, active_topic, max_topics);

    assert(widget.is_for_stream(stream_id));
    assert.equal(widget.get_parent(), parent_elem);

    assert(checked_mutes);
    assert(rendered);
    assert(item_appended);
    assert(attached_to_parent);

    assert.equal(topic_list.active_stream_id(), stream_id);
}());
