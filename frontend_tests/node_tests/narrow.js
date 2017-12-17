zrequire('hash_util');
zrequire('hashchange');
zrequire('narrow_state');
zrequire('people');
zrequire('stream_data');
zrequire('util');
zrequire('Filter', 'js/filter');

zrequire('narrow');

set_global('topic_data', {
});

set_global('window', {
    location : {
        hash : 'foobar',
    },
});

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

(function test_by_stream_topic_name() {
    var stream_ids = {
        Veronica : 10,
        Rome : 21,
        zulip : 31,
    };
    var all_topics = {
        10 : ['Veronica1', 'Veronica2'],
        21 : [],
        31 : ['issue1'],
    };
    stream_data.get_stream_id = function (stream) {
        return stream_ids[stream];
    };
    topic_data.get_recent_names = function (stream_id) {
        return all_topics[stream_id];
    };



    function get_operators(stream, topic) {
        var operators;
        narrow.activate = function (raw_operators) {
            operators = raw_operators;
            return;
        };
        narrow.by_stream_topic_name(stream, topic);
        return operators;
    }

    // Both stream and Topic are existing
    assert.deepEqual(get_operators('Veronica', 'Veronica1'), [
        {operator: 'stream', operand: 'Veronica'},
        {operator: 'topic', operand: 'Veronica1'},
    ]);

    // Only stream
    assert.deepEqual(get_operators('Veronica', ''), [
        {operator: 'stream', operand: 'Veronica'},
    ]);

    // Stream with incorrect topic
    assert.deepEqual(get_operators('Veronica', 'Ver'), [
        {operator: 'stream', operand: 'Veronica'},
    ]);

    // Stream with no topics in it
    assert.deepEqual(get_operators('Rome', 'rome1'), [
        {operator: 'stream', operand: 'Rome'},
    ]);

    // A topic with no stream
    assert.deepEqual(get_operators('', 'Veronica2'), undefined);
}());

(function test_by_recipient_name() {

    function get_narrow_call(recipient) {
        var called = '';
        narrow.by = function (type) {
            called = type;
        };
        narrow.by_recipient_name(recipient);
        return called;
    }

    var valid_emails = ['aaron@zulip.com', 'iago@github.com'];
    people.is_valid_email_for_compose = function (email) {
        return valid_emails.includes(email);
    };

    people.email_list_to_user_ids_string = function () {};

    // Invalid recipient
    assert.equal(get_narrow_call('foo@zulip.com'), 'is');
    assert.equal(get_narrow_call(''), 'is');
    assert.equal(get_narrow_call('foo@zulip.com, aaron@zulip.com'), 'is');

    // Valid recipient with different types of input
    assert.equal(get_narrow_call('aaron@zulip.com'), 'pm-with');
    assert.equal(get_narrow_call('aaron@zulip.com, iago@github.com'), 'pm-with');
    assert.equal(get_narrow_call('aaron@zulip.com,iago@github.com, '), 'pm-with');

}());

(function test_to_compose_target() {
    set_global('compose_state', {
    });

    set_global('compose_actions', {
        start : function () {},
    });

    function get_narrow_call() {
        var narrow_by;
        narrow.by_stream_topic_name = function () {
            narrow_by = 'by_stream_topic_name';
        };
        narrow.by_recipient_name = function () {
            narrow_by = 'by_recipient_name';
        };
        narrow.to_compose_target();
        return narrow_by;
    }

    // Test if get_message_type is neither 'stream' nor 'private'
    compose_state.get_message_type =  function () {
        return '';
    };
    assert.equal(narrow.to_compose_target(), false);

    // Test sending message to stream
    compose_state.get_message_type =  function () {
        return 'stream';
    };

    // Test if stream is empty
    compose_state.stream_name = function () {
        return '';
    };
    assert.equal(narrow.to_compose_target(), false);

    // Test if stream is non empty with different topics.

    _.each(['alpha', 'gamma'], function (stream_name) {
        _.each(['', 'alpha-beta'], function (subject) {
            compose_state.stream_name = function () {
                return stream_name;
            };
            compose_state.subject = function () {
                return subject;
            };
            assert.equal(get_narrow_call(), 'by_stream_topic_name');
        });
    });

    // Test sending private message
    compose_state.get_message_type =  function () {
        return 'private';
    };
    _.each(['', 'alpha@beta.com, ', 'alpha@beta.com, gamma@beta.com'], function (recipient) {
        compose_state.recipient = function () {
            return recipient;
        };
        assert.equal(get_narrow_call(),'by_recipient_name');
    });

}());
