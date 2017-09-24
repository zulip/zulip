zrequire('hash_util');
zrequire('hashchange');
zrequire('narrow_state');
zrequire('people');
zrequire('stream_data');
zrequire('Filter', 'js/filter');

zrequire('narrow');

var narrow_state = global.narrow_state;

var Filter = global.Filter;
var stream_data = global.stream_data;
var _ = global._;

function set_filter(operators) {
    operators = _.map(operators, function (op) {
        return {operator: op[0], operand: op[1]};
    });
    narrow_state.set_current_filter(new Filter(operators));
}

(function test_stream_topic() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar'], ['search', 'Yo']]);

    set_global('current_msg_list', {
    });

    global.current_msg_list.selected_message = function () {};

    var stream_topic = narrow.stream_topic();

    assert.deepEqual(stream_topic, {
        stream: 'Foo',
        topic: 'Bar',
    });

    global.current_msg_list.selected_message = function () {
        return {
            stream: 'Stream1',
            subject: 'Topic1',
        };
    };

    stream_topic = narrow.stream_topic();

    assert.deepEqual(stream_topic, {
        stream: 'Stream1',
        topic: 'Topic1',
    });

}());

(function test_uris() {
    var ray = {
        email: 'ray@example.com',
        user_id: 22,
        full_name: 'Raymond',
    };
    people.add(ray);

    var alice = {
        email: 'alice@example.com',
        user_id: 23,
        full_name: 'Alice Smith',
    };
    people.add(alice);

    var uri = narrow.pm_with_uri(ray.email);
    assert.equal(uri, '#narrow/pm-with/22-ray');

    uri = narrow.huddle_with_uri("22,23");
    assert.equal(uri, '#narrow/pm-with/22,23-group');

    uri = narrow.by_sender_uri(ray.email);
    assert.equal(uri, '#narrow/sender/22-ray');

    var emails = global.hash_util.decode_operand('pm-with', '22,23-group');
    assert.equal(emails, 'alice@example.com,ray@example.com');
}());

(function test_show_empty_narrow_message() {

    var hide_id;
    var show_id;
    global.$ = function (id) {
      return {hide: function () {hide_id = id;}, show: function () {show_id = id;}};
    };

    narrow_state.reset_current_filter();
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_message');

    // for non-existent or private stream
    set_filter([['stream', 'Foo']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#nonsubbed_private_nonexistent_stream_narrow_message');

    // for non sub public stream
    stream_data.add_sub('ROME', {name: 'ROME', stream_id: 99});
    set_filter([['stream', 'Rome']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#nonsubbed_stream_narrow_message');

    set_filter([['is', 'starred']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_star_narrow_message');

    set_filter([['is', 'mentioned']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_all_mentioned');

    set_filter([['is', 'private']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_all_private_message');

    set_filter([['is', 'unread']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#no_unread_narrow_message');

    set_filter([['pm-with', ['alice@example.com', 'Yo']]]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_multi_private_message');

    set_filter([['pm-with', 'alice@example.com']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_private_message');

    set_filter([['group-pm-with', 'alice@example.com']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_group_private_message');

    set_filter([['sender', 'ray@example.com']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#silent_user');

    set_filter([['sender', 'sinwar@example.com']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#non_existing_user');

    set_filter([['search', 'grail']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_search_narrow_message');
}());
