set_global('$', global.make_zjquery());
zrequire('hash_util');
zrequire('hashchange');
zrequire('narrow_state');
zrequire('people');
zrequire('stream_data');
zrequire('util');
zrequire('Filter', 'js/filter');
set_global('i18n', global.stub_i18n);
set_global('page_params', {
    stop_words: ['what', 'about'],
});

zrequire('narrow');

function set_filter(operators) {
    operators = _.map(operators, function (op) {
        return {operator: op[0], operand: op[1]};
    });
    narrow_state.set_current_filter(new Filter(operators));
}

var me = {
    email: 'me@example.com',
    user_id: 5,
    full_name: 'Me Myself',
};

var alice = {
    email: 'alice@example.com',
    user_id: 23,
    full_name: 'Alice Smith',
};

var ray = {
    email: 'ray@example.com',
    user_id: 22,
    full_name: 'Raymond',
};

run_test('stream_topic', () => {
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
            topic: 'Topic1',
        };
    };

    stream_topic = narrow.stream_topic();

    assert.deepEqual(stream_topic, {
        stream: 'Stream1',
        topic: 'Topic1',
    });

});

run_test('uris', () => {
    people.add(ray);
    people.add(alice);
    people.add(me);
    people.initialize_current_user(me.user_id);

    var uri = hash_util.pm_with_uri(ray.email);
    assert.equal(uri, '#narrow/pm-with/22-ray');

    uri = hash_util.huddle_with_uri("22,23");
    assert.equal(uri, '#narrow/pm-with/22,23-group');

    uri = hash_util.by_sender_uri(ray.email);
    assert.equal(uri, '#narrow/sender/22-ray');

    var emails = global.hash_util.decode_operand('pm-with', '22,23-group');
    assert.equal(emails, 'alice@example.com,ray@example.com');

    emails = global.hash_util.decode_operand('pm-with', '5,22,23-group');
    assert.equal(emails, 'alice@example.com,ray@example.com');

    emails = global.hash_util.decode_operand('pm-with', '5-group');
    assert.equal(emails, 'me@example.com');
});

run_test('show_empty_narrow_message', () => {
    narrow_state.reset_current_filter();
    narrow.show_empty_narrow_message();
    assert.equal($('.empty_feed_notice').visible(), false);
    assert($('#empty_narrow_message').visible());
    assert.equal(
        $('#left_bar_compose_reply_button_big').attr('title'),
        'translated: There are no messages to reply to.'
    );

    // for non-existent or private stream
    set_filter([['stream', 'Foo']]);
    narrow.show_empty_narrow_message();
    assert($('#nonsubbed_private_nonexistent_stream_narrow_message').visible());

    // for non sub public stream
    stream_data.add_sub('ROME', {name: 'ROME', stream_id: 99});
    set_filter([['stream', 'Rome']]);
    narrow.show_empty_narrow_message();
    assert($('#nonsubbed_stream_narrow_message').visible());

    set_filter([['is', 'starred']]);
    narrow.show_empty_narrow_message();
    assert($('#empty_star_narrow_message').visible());

    set_filter([['is', 'mentioned']]);
    narrow.show_empty_narrow_message();
    assert($('#empty_narrow_all_mentioned').visible());

    set_filter([['is', 'private']]);
    narrow.show_empty_narrow_message();
    assert($('#empty_narrow_all_private_message').visible());

    set_filter([['is', 'unread']]);
    narrow.show_empty_narrow_message();
    assert($('#no_unread_narrow_message').visible());

    set_filter([['pm-with', ['Yo']]]);
    narrow.show_empty_narrow_message();
    assert($('#non_existing_user').visible());

    people.add_in_realm(alice);
    set_filter([['pm-with', ['alice@example.com', 'Yo']]]);
    narrow.show_empty_narrow_message();
    assert($('#non_existing_users').visible());

    set_filter([['pm-with', 'alice@example.com']]);
    narrow.show_empty_narrow_message();
    assert($('#empty_narrow_private_message').visible());

    set_filter([['group-pm-with', 'alice@example.com']]);
    narrow.show_empty_narrow_message();
    assert($('#empty_narrow_group_private_message').visible());

    set_filter([['sender', 'ray@example.com']]);
    narrow.show_empty_narrow_message();
    assert($('#silent_user').visible());

    set_filter([['sender', 'sinwar@example.com']]);
    narrow.show_empty_narrow_message();
    assert($('#non_existing_user').visible());

    var display = $("#empty_search_stop_words_string");

    var items = [];
    display.append = (html) => {
        items.push(html);
    };

    set_filter([['search', 'grail']]);
    narrow.show_empty_narrow_message();
    assert($('#empty_search_narrow_message').visible());

    assert.equal(items.length, 2);
    assert.equal(items[0], ' ');
    assert.equal(items[1].text(), 'grail');

    items = [];
    display.append = (html) => {
        if (html.text) {
            items.push(html.selector + html.text());
        }
    };

    set_filter([['search', 'what about grail']]);
    narrow.show_empty_narrow_message();
    assert($('#empty_search_narrow_message').visible());

    assert.equal(items.length, 3);
    assert.equal(items[0], '<del>what');
    assert.equal(items[1], '<del>about');
    assert.equal(items[2], '<span>grail');
});

run_test('narrow_to_compose_target', () => {
    set_global('compose_state', {});
    set_global('topic_data', {});
    const args = {called: false};
    const activate_backup = narrow.activate;
    narrow.activate = function (operators, opts) {
        args.operators = operators;
        args.opts = opts;
        args.called = true;
    };

    // No-op when not composing.
    global.compose_state.composing = () => false;
    narrow.to_compose_target();
    assert.equal(args.called, false);
    global.compose_state.composing = () => true;

    // No-op when empty stream.
    global.compose_state.get_message_type = () => 'stream';
    global.compose_state.stream_name = () => '';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, false);

    // --- Tests for stream messages ---
    global.compose_state.get_message_type = () => 'stream';
    stream_data.add_sub('ROME', {name: 'ROME', stream_id: 99});
    global.compose_state.stream_name = () => 'ROME';
    global.topic_data.get_recent_names = () => ['one', 'two', 'three'];

    // Test with existing topic
    global.compose_state.topic = () => 'one';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.equal(args.opts.trigger, 'narrow_to_compose_target');
    assert.deepEqual(args.operators, [
        {operator: 'stream', operand: 'ROME'},
        {operator: 'topic', operand: 'one'},
    ]);

    // Test with new topic
    global.compose_state.topic = () => 'four';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'stream', operand: 'ROME'},
    ]);

    // Test with blank topic
    global.compose_state.topic = () => '';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'stream', operand: 'ROME'},
    ]);

    // Test with no topic
    global.compose_state.topic = () => {};
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'stream', operand: 'ROME'},
    ]);

    // --- Tests for PMs ---
    global.compose_state.get_message_type = () => 'private';
    people.add_in_realm(ray);
    people.add_in_realm(alice);
    people.add_in_realm(me);

    // Test with valid person
    global.compose_state.recipient = () => 'alice@example.com';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'pm-with', operand: 'alice@example.com'},
    ]);

    // Test with valid persons
    global.compose_state.recipient = () => 'alice@example.com,ray@example.com';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'pm-with', operand: 'alice@example.com,ray@example.com'},
    ]);

    // Test with some inavlid persons
    global.compose_state.recipient = () => 'alice@example.com,random,ray@example.com';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'is', operand: 'private'},
    ]);

    // Test with all inavlid persons
    global.compose_state.recipient = () => 'alice,random,ray';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'is', operand: 'private'},
    ]);

    // Test with no persons
    global.compose_state.recipient = () => '';
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.operators, [
        {operator: 'is', operand: 'private'},
    ]);

    narrow.activate = activate_backup;
});
