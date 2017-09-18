var noop = function () {};
var return_false = function () { return false; };
var return_true = function () { return true; };

set_global('document', {
    location: {
    },
});

set_global('page_params', {
    use_websockets: false,
});

set_global('$', function () {
});

add_dependencies({
    compose: 'js/compose',
});

set_global('$', global.make_zjquery());

add_dependencies({
    compose_state: 'js/compose_state',
    people: 'js/people',
    util: 'js/util',
    compose_ui: 'js/compose_ui',
});

var compose_actions = require('js/compose_actions.js');

var start = compose_actions.start;
var cancel = compose_actions.cancel;
var get_focus_area = compose_actions._get_focus_area;
var respond_to_message = compose_actions.respond_to_message;
var reply_with_mention = compose_actions.reply_with_mention;

var compose_state = global.compose_state;

set_global('reload', {
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
    mark_message_as_read: noop,
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

function assert_visible(sel) {
    assert($(sel).visible());
}

function assert_hidden(sel) {
    assert(!$(sel).visible());
}

(function test_initial_state() {
    assert.equal(compose_state.composing(), false);
    assert.equal(compose_state.get_message_type(), false);
    assert.equal(compose_state.has_message_content(), false);
}());

(function test_start() {
    compose_actions.autosize_message_content = noop;
    compose_actions.expand_compose_box = noop;
    compose_actions.set_focus = noop;
    compose_actions.complete_starting_tasks = noop;
    compose_actions.blur_textarea = noop;
    compose_actions.clear_textarea = noop;

    // Start stream message
    global.narrow_state.set_compose_defaults = function (opts) {
        opts.stream = 'stream1';
        opts.subject = 'topic1';
    };

    var opts = {};
    start('stream', opts);

    assert_visible('#stream-message');
    assert_hidden('#private-message');

    assert.equal($('#stream').val(), 'stream1');
    assert.equal($('#subject').val(), 'topic1');
    assert.equal(compose_state.get_message_type(), 'stream');
    assert(compose_state.composing());

    // Start PM
    global.narrow_state.set_compose_defaults = function (opts) {
        opts.private_message_recipient = 'foo@example.com';
    };

    opts = {
        content: 'hello',
    };

    $('#new_message_content').trigger = noop;
    start('private', opts);

    assert_hidden('#stream-message');
    assert_visible('#private-message');

    assert.equal($('#private_message_recipient').val(), 'foo@example.com');
    assert.equal($('#new_message_content').val(), 'hello');
    assert.equal(compose_state.get_message_type(), 'private');
    assert(compose_state.composing());

    // Cancel compose.
    assert_hidden('#compose_controls');
    cancel();
    assert_visible('#compose_controls');
    assert_hidden('#private-message');
    assert(!compose_state.composing());
}());

(function test_respond_to_message() {
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
    assert.equal($('#private_message_recipient').val(), 'alice@example.com');

    // Test stream
    msg = {
        type: 'stream',
        stream: 'devel',
        subject: 'python',
        reply_to: 'bob', // compose.start needs this for dubious reasons
    };
    stub_selected_message(msg);

    opts = {
    };

    respond_to_message(opts);
    assert.equal($('#stream').val(), 'devel');
}());

(function test_reply_with_mention() {
    var msg = {
        type: 'stream',
        stream: 'devel',
        subject: 'python',
        reply_to: 'bob', // compose.start needs this for dubious reasons
        sender_full_name: 'Bob Roberts',
    };
    stub_selected_message(msg);

    var opts = {
    };

    reply_with_mention(opts);
    assert.equal($('#stream').val(), 'devel');
    assert.equal($('#new_message_content').val(), '@**Bob Roberts** ');
    assert(compose_state.has_message_content());
}());

(function test_get_focus_area() {
    assert.equal(get_focus_area('private', {}), 'private_message_recipient');
    assert.equal(get_focus_area('private', {
        private_message_recipient: 'bob@example.com'}), 'new_message_content');
    assert.equal(get_focus_area('stream', {}), 'stream');
    assert.equal(get_focus_area('stream', {stream: 'fun'}),
                 'subject');
    assert.equal(get_focus_area('stream', {stream: 'fun',
                                           subject: 'more'}),
                 'new_message_content');
    assert.equal(get_focus_area('stream', {stream: 'fun',
                                           subject: 'more',
                                           trigger: 'new topic button'}),
                 'subject');
}());

(function test_focus_in_empty_compose() {
    $('#new_message_content').is = function (attr) {
        assert.equal(attr, ':focus');
        return $('#new_message_content').is_focused;
    };

    compose_state.composing = return_true;
    $('#new_message_content').val('');
    $('#new_message_content').focus();
    assert(compose_state.focus_in_empty_compose());

    compose_state.composing = return_false;
    assert(!compose_state.focus_in_empty_compose());

    $('#new_message_content').val('foo');
    assert(!compose_state.focus_in_empty_compose());

    $('#new_message_content').blur();
    assert(!compose_state.focus_in_empty_compose());
}());
