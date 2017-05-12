global.stub_out_jquery();

add_dependencies({
    hash_util: 'js/hash_util.js',
    hashchange: 'js/hashchange.js',
    narrow_state: 'js/narrow_state.js',
    people: 'js/people.js',
    stream_data: 'js/stream_data.js',
    Filter: 'js/filter.js',
});

var narrow = require('js/narrow.js');

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

(function test_stream() {
    var test_stream = {name: 'Test', stream_id: 15};
    stream_data.add_sub('Test', test_stream);

    assert(!narrow_state.is_for_stream_id(test_stream.stream_id));

    set_filter([['stream', 'Test'], ['topic', 'Bar'], ['search', 'yo']]);

    assert.equal(narrow_state.stream(), 'Test');
    assert.equal(narrow_state.topic(), 'Bar');
    assert(narrow_state.is_for_stream_id(test_stream.stream_id));
}());


(function test_narrowed() {
    narrow_state.reset_current_filter(); // not narrowed, basically
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());

    set_filter([['stream', 'Foo']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());

    set_filter([['pm-with', 'steve@zulip.com']]);
    assert(narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());

    set_filter([['stream', 'Foo'], ['topic', 'bar']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(narrow_state.narrowed_by_topic_reply());
    assert(!narrow_state.narrowed_to_search());
    assert(narrow_state.narrowed_to_topic());

    set_filter([['search', 'grail']]);
    assert(!narrow_state.narrowed_to_pms());
    assert(!narrow_state.narrowed_by_reply());
    assert(!narrow_state.narrowed_by_pm_reply());
    assert(!narrow_state.narrowed_by_topic_reply());
    assert(narrow_state.narrowed_to_search());
    assert(!narrow_state.narrowed_to_topic());
}());

(function test_operators() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar'], ['search', 'Yo']]);
    var result = narrow_state.operators();
    assert.equal(result.length, 3);
    assert.equal(result[0].operator, 'stream');
    assert.equal(result[0].operand, 'Foo');

    assert.equal(result[1].operator, 'topic');
    assert.equal(result[1].operand, 'Bar');

    assert.equal(result[2].operator, 'search');
    assert.equal(result[2].operand, 'yo');
}());

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

(function test_muting_enabled() {
    set_filter([['stream', 'devel']]);
    assert(narrow_state.muting_enabled());

    narrow_state.reset_current_filter(); // not narrowed, basically
    assert(narrow_state.muting_enabled());

    set_filter([['stream', 'devel'], ['topic', 'mac']]);
    assert(!narrow_state.muting_enabled());

    set_filter([['search', 'whatever']]);
    assert(!narrow_state.muting_enabled());

    set_filter([['is', 'private']]);
    assert(!narrow_state.muting_enabled());

}());

(function test_set_compose_defaults() {
    set_filter([['stream', 'Foo'], ['topic', 'Bar']]);

    var opts = {};
    narrow_state.set_compose_defaults(opts);
    assert.equal(opts.stream, 'Foo');
    assert.equal(opts.subject, 'Bar');

    stream_data.add_sub('ROME', {name: 'ROME', stream_id: 99});
    set_filter([['stream', 'rome']]);

    opts = {};
    narrow_state.set_compose_defaults(opts);
    assert.equal(opts.stream, 'ROME');
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

    set_filter([['pm-with', ['alice@example.com', 'Yo']]]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_multi_private_message');

    set_filter([['pm-with', 'alice@example.com']]);
    narrow.show_empty_narrow_message();
    assert.equal(hide_id,'.empty_feed_notice');
    assert.equal(show_id, '#empty_narrow_private_message');

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

(function test_update_email() {
    var steve = {
        email: 'steve@foo.com',
        user_id: 43,
        full_name: 'Steve',
    };

    people.add(steve);
    set_filter([
        ['pm-with', 'steve@foo.com'],
        ['sender', 'steve@foo.com'],
        ['stream', 'steve@foo.com'], // try to be tricky
    ]);
    narrow_state.update_email(steve.user_id, 'showell@foo.com');
    var filter = narrow_state.filter();
    assert.deepEqual(filter.operands('pm-with'), ['showell@foo.com']);
    assert.deepEqual(filter.operands('sender'), ['showell@foo.com']);
    assert.deepEqual(filter.operands('stream'), ['steve@foo.com']);
}());
