var noop = function () {};
var return_false = function () { return false; };
var return_true = function () { return true; };

set_global('document', {
    location: {}, // we need this to load compose.js
});

set_global('page_params', {
    use_websockets: false,
});

set_global('$', global.make_zjquery());

set_global('compose_pm_pill', {
});

zrequire('people');
zrequire('compose_ui');
zrequire('compose');
zrequire('util');
zrequire('compose_state');
zrequire('compose_actions');

set_global('document', 'document-stub');

var start = compose_actions.start;
var cancel = compose_actions.cancel;
var get_focus_area = compose_actions._get_focus_area;
var respond_to_message = compose_actions.respond_to_message;
var reply_with_mention = compose_actions.reply_with_mention;
var quote_and_reply = compose_actions.quote_and_reply;

var compose_state = global.compose_state;

compose_state.recipient = (function () {
    var recipient;

    return function (arg) {
        if (arg === undefined) {
            return recipient;
        }

        recipient = arg;
    };
}());

set_global('reload_state', {
    is_in_progress: return_false,
});

set_global('notifications', {
    clear_compose_notifications: noop,
});

set_global('compose_fade', {
    clear_compose: noop,
});

set_global('drafts', {
    update_draft: noop,
});

set_global('resize', {
    resize_bottom_whitespace: noop,
});

set_global('narrow_state', {
    set_compose_defaults: noop,
});

set_global('unread_ops', {
    notify_server_message_read: noop,
});

set_global('common', {
    status_classes: 'status_classes',
});

function stub_selected_message(msg) {
    set_global('current_msg_list', {
        selected_message: function () {
            return msg;
        },
    });
}

function stub_channel_get(success_value) {
    set_global('channel', {
        get: function (opts) {
            opts.success(success_value);
        },
    });
}

function assert_visible(sel) {
    assert($(sel).visible());
}

function assert_hidden(sel) {
    assert(!$(sel).visible());
}

run_test('initial_state', () => {
    assert.equal(compose_state.composing(), false);
    assert.equal(compose_state.get_message_type(), false);
    assert.equal(compose_state.has_message_content(), false);
});

run_test('start', () => {
    compose_actions.autosize_message_content = noop;
    compose_actions.expand_compose_box = noop;
    compose_actions.set_focus = noop;
    compose_actions.complete_starting_tasks = noop;
    compose_actions.blur_textarea = noop;
    compose_actions.clear_textarea = noop;

    // Start stream message
    global.narrow_state.set_compose_defaults = function () {
        var opts = {};
        opts.stream = 'stream1';
        opts.topic = 'topic1';
        return opts;
    };

    var opts = {};
    start('stream', opts);

    assert_visible('#stream-message');
    assert_hidden('#private-message');

    assert.equal($('#stream_message_recipient_stream').val(), 'stream1');
    assert.equal($('#stream_message_recipient_topic').val(), 'topic1');
    assert.equal(compose_state.get_message_type(), 'stream');
    assert(compose_state.composing());

    // Start PM
    global.narrow_state.set_compose_defaults = function () {
        var opts = {};
        opts.private_message_recipient = 'foo@example.com';
        return opts;
    };

    opts = {
        content: 'hello',
    };

    $('#compose-textarea').trigger = noop;
    start('private', opts);

    assert_hidden('#stream-message');
    assert_visible('#private-message');

    assert.equal(compose_state.recipient(), 'foo@example.com');
    assert.equal($('#compose-textarea').val(), 'hello');
    assert.equal(compose_state.get_message_type(), 'private');
    assert(compose_state.composing());

    // Cancel compose.
    var pill_cleared;

    compose_pm_pill.clear = function () {
        pill_cleared = true;
    };

    assert_hidden('#compose_controls');
    cancel();
    assert(pill_cleared);
    assert_visible('#compose_controls');
    assert_hidden('#private-message');
    assert(!compose_state.composing());
});

run_test('respond_to_message', () => {
    // Test PM
    var person = {
        user_id: 22,
        email: 'alice@example.com',
        full_name: 'Alice',
    };
    people.add_in_realm(person);

    var msg = {
        type: 'private',
        sender_id: person.user_id,
    };
    stub_selected_message(msg);

    var opts = {
        reply_type: 'personal',
    };

    respond_to_message(opts);
    assert.equal(compose_state.recipient(), 'alice@example.com');

    // Test stream
    msg = {
        type: 'stream',
        stream: 'devel',
        topic: 'python',
        reply_to: 'bob', // compose.start needs this for dubious reasons
    };
    stub_selected_message(msg);

    opts = {
    };

    respond_to_message(opts);
    assert.equal($('#stream_message_recipient_stream').val(), 'devel');
});

run_test('reply_with_mention', () => {
    var msg = {
        type: 'stream',
        stream: 'devel',
        topic: 'python',
        reply_to: 'bob', // compose.start needs this for dubious reasons
        sender_full_name: 'Bob Roberts',
        sender_id: 40,
    };
    stub_selected_message(msg);

    var syntax_to_insert;
    compose_ui.insert_syntax_and_focus = function (syntax) {
        syntax_to_insert = syntax;
    };

    var opts = {
    };

    reply_with_mention(opts);
    assert.equal($('#stream_message_recipient_stream').val(), 'devel');
    assert.equal(syntax_to_insert, '@**Bob Roberts**');
    assert(compose_state.has_message_content());

    // Test for extended mention syntax
    var bob_1 = {
        user_id: 30,
        email: 'bob1@example.com',
        full_name: 'Bob Roberts',
    };
    people.add_in_realm(bob_1);
    var bob_2 = {
        user_id: 40,
        email: 'bob2@example.com',
        full_name: 'Bob Roberts',
    };
    people.add_in_realm(bob_2);

    reply_with_mention(opts);
    assert.equal($('#stream_message_recipient_stream').val(), 'devel');
    assert.equal(syntax_to_insert, '@**Bob Roberts|40**');
    assert(compose_state.has_message_content());
});

run_test('quote_and_reply', () => {
    var msg = {
        type: 'stream',
        stream: 'devel',
        topic: 'python',
        reply_to: 'bob',
        sender_full_name: 'Bob Roberts',
        sender_id: 40,
    };
    stub_selected_message(msg);
    stub_channel_get({ raw_content: 'Testing.' });

    current_msg_list.selected_id = function () {
        return 100;
    };

    compose_ui.insert_syntax_and_focus = function (syntax) {
        assert.equal(syntax, '[Quoting…]\n');
    };

    compose_ui.replace_syntax = function (syntax, replacement) {
        assert.equal(syntax, '[Quoting…]');
        assert.equal(replacement, '```quote\nTesting.\n```');
    };

    var opts = {
        reply_type: 'personal',
    };

    $('#compose-textarea').caret = (pos) => {
        assert.equal(pos, 0);
    };

    quote_and_reply(opts);

    current_msg_list.selected_message = function () {
        return {
            type: 'stream',
            stream: 'devel',
            topic: 'test',
            reply_to: 'bob',
            sender_full_name: 'Bob',
            sender_id: 40,
            raw_content: 'Testing.',
        };
    };

    channel.get = function () {
        assert.fail('channel.get should not be used if raw_content is present');
    };

    quote_and_reply(opts);
});

run_test('get_focus_area', () => {
    assert.equal(get_focus_area('private', {}), '#private_message_recipient');
    assert.equal(get_focus_area('private', {
        private_message_recipient: 'bob@example.com'}), '#compose-textarea');
    assert.equal(get_focus_area('stream', {}), '#stream_message_recipient_stream');
    assert.equal(get_focus_area('stream', {stream: 'fun'}),
                 '#stream_message_recipient_topic');
    assert.equal(get_focus_area('stream', {stream: 'fun',
                                           topic: 'more'}),
                 '#compose-textarea');
    assert.equal(get_focus_area('stream', {stream: 'fun',
                                           topic: 'more',
                                           trigger: 'new topic button'}),
                 '#stream_message_recipient_topic');
});

run_test('focus_in_empty_compose', () => {
    $('#compose-textarea').is = function (attr) {
        assert.equal(attr, ':focus');
        return $('#compose-textarea').is_focused;
    };

    compose_state.composing = return_true;
    $('#compose-textarea').val('');
    $('#compose-textarea').focus();
    assert(compose_state.focus_in_empty_compose());

    compose_state.composing = return_false;
    assert(!compose_state.focus_in_empty_compose());

    $('#compose-textarea').val('foo');
    assert(!compose_state.focus_in_empty_compose());

    $('#compose-textarea').blur();
    assert(!compose_state.focus_in_empty_compose());
});

run_test('on_narrow', () => {
    var cancel_called = false;
    compose_actions.cancel = function () {
        cancel_called = true;
    };
    compose_actions.on_narrow({
        force_close: true,
    });
    assert(cancel_called);

    var on_topic_narrow_called = false;
    compose_actions.on_topic_narrow = function () {
        on_topic_narrow_called = true;
    };
    narrow_state.narrowed_by_topic_reply = function () {
        return true;
    };
    compose_actions.on_narrow({
        force_close: false,
    });
    assert(on_topic_narrow_called);

    var update_message_list_called = false;
    narrow_state.narrowed_by_topic_reply = function () {
        return false;
    };
    compose_fade.update_message_list = function () {
        update_message_list_called = true;
    };
    compose_state.has_message_content = function () {
        return true;
    };
    compose_actions.on_narrow({
        force_close: false,
    });
    assert(update_message_list_called);

    compose_state.has_message_content = function () {
        return false;
    };
    var start_called = false;
    compose_actions.start = function () {
        start_called = true;
    };
    narrow_state.narrowed_by_pm_reply = function () {
        return true;
    };
    compose_actions.on_narrow({
        force_close: false,
        trigger: 'not-search',
        private_message_recipient: 'not@empty.com',
    });
    assert(start_called);

    start_called = false;
    compose_actions.on_narrow({
        force_close: false,
        trigger: 'search',
        private_message_recipient: '',
    });
    assert(!start_called);

    narrow_state.narrowed_by_pm_reply = function () {
        return false;
    };
    cancel_called = false;
    compose_actions.on_narrow({
        force_close: false,
    });
    assert(cancel_called);
});
