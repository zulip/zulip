var assert = require('assert');
var _ = global._;

var noop = function () {};

// The next section of cruft will go away when we can pull out
// dispatcher from server_events.
(function work_around_server_events_loading_issues() {
    add_dependencies({
        util: 'js/util.js',
    });
    set_global('document', {});
    set_global('window', {
        addEventListener: noop,
    });
    global.stub_out_jquery();
}());

// These dependencies are closer to the dispatcher, and they
// apply to all tests.
set_global('tutorial', {
    is_running: function () {
        return false;
    },
});
set_global('home_msg_list', {
    rerender: noop,
    select_id: noop,
    selected_id: function () {return 1;},
});
set_global('echo', {
    process_from_server: function (messages) {
        return messages;
    },
    set_realm_filters: noop,
});

// page_params is highly coupled to dispatching now
set_global('page_params', {test_suite: false});
var page_params = global.page_params;

// alert_words is coupled to dispatching in the sense
// that we write directly to alert_words.words
add_dependencies({alert_words: 'js/alert_words.js'});

// we also directly write to pointer
set_global('pointer', {});

// We access various msg_list object to rerender them
set_global('current_msg_list', {rerender: noop});

var server_events = require('js/server_events.js');

// This also goes away if we can isolate the dispatcher.  We
// have to call it after doing the require on server_events.js,
// so that it can set a private variable for us that bypasses
// code that queue up events and early-exits.
server_events.home_view_loaded();

// This jQuery shim can go away when we remove $.each from
// server_events.js.  (It's a simple change that just
// requires some manual testing.)
$.each = function (data, f) {
    _.each(data, function (value, key) {
        f(key, value);
    });
};

// Set up our dispatch function to point to _get_events_success
// now.
function dispatch(ev) {
    server_events._get_events_success([ev]);
}


// TODO: These events are not guaranteed to be perfectly
//       representative of what the server sends.  For
//       now we just want very basic test coverage.  We
//       have more mature tests for events on the backend
//       side in test_events.py, and we may be able to
//       re-work both sides (js/python) so that we work off
//       a shared fixture.
var event_fixtures = {
    alert_words: {
        type: 'alert_words',
        alert_words: ['fire', 'lunch'],
    },

    default_streams: {
        type: 'default_streams',
        default_streams: [
            {
                name: 'devel',
                description: 'devel',
                invite_only: false,
                stream_id: 1,
            },
            {
                name: 'test',
                description: 'test',
                invite_only: true,
                stream_id: 1,
            },
        ],
    },

    message: {
        type: 'message',
        message: {
            content: 'hello',
        },
        flags: [],
    },

    muted_topics: {
        type: 'muted_topics',
        muted_topics: [['devel', 'js'], ['lunch', 'burritos']],
    },

    pointer: {
        type: 'pointer',
        pointer: 999,
    },

    presence: {
        type: 'presence',
        email: 'alice@example.com',
        presence: {
            client_name: 'electron',
            is_mirror_dummy: false,
            // etc.
        },
        server_timestamp: 999999,
    },

    // Please keep this next section un-nested, as we want this to partly
    // be simple documentation on the formats of individual events.
    realm__update__create_stream_by_admins_only: {
        type: 'realm',
        op: 'update',
        property: 'create_stream_by_admins_only',
        value: false,
    },

    realm__update__invite_by_admins_only: {
        type: 'realm',
        op: 'update',
        property: 'invite_by_admins_only',
        value: false,
    },

    realm__update__invite_required: {
        type: 'realm',
        op: 'update',
        property: 'invite_required',
        value: false,
    },

    realm__update__name: {
        type: 'realm',
        op: 'update',
        property: 'name',
        value: 'new_realm_name',
    },

    realm__update__restricted_to_domain: {
        type: 'realm',
        op: 'update',
        property: 'restricted_to_domain',
        value: false,
    },

    realm__update_dict__default: {
        type: 'realm',
        op: 'update_dict',
        property: 'default',
        data: {
            allow_message_editing: true,
            message_content_edit_limit_seconds: 5,
        },
    },

    realm_bot__add: {
        type: 'realm_bot',
        op: 'add',
        bot: {
            email: 'the-bot@example.com',
            full_name: 'The Bot',
            // etc.
        },
    },

    realm_bot__remove: {
        type: 'realm_bot',
        op: 'remove',
        bot: {
            email: 'the-bot@example.com',
            full_name: 'The Bot',
        },
    },

    realm_bot__update: {
        type: 'realm_bot',
        op: 'update',
        bot: {
            email: 'the-bot@example.com',
            user_id: 4321,
            full_name: 'The Bot Has A New Name',
        },
    },

    realm_emoji: {
        type: 'realm_emoji',
        realm_emoji: {
            airplane: {
                display_url: 'some_url',
            },
        },
    },

    realm_filters: {
        type: 'realm_filters',
        realm_filters: [
            ['#[123]', 'ticket %(id)s'],
        ],
    },

    realm_user__add: {
        type: 'realm_user',
        op: 'add',
        person: {
            email: 'alice@example.com',
            full_name: 'Alice User',
            // etc.
        },
    },

    realm_user__remove: {
        type: 'realm_user',
        op: 'remove',
        person: {
            email: 'alice@example.com',
            full_name: 'Alice User',
            // etc.
        },
    },

    realm_user__update: {
        type: 'realm_user',
        op: 'update',
        person: {
            email: 'alice@example.com',
            full_name: 'Alice NewName',
            // etc.
        },
    },

    referral: {
        type: 'referral',
        referrals: {
            granted: 10,
            used: 5,
        },
    },

    restart: {
        type: 'restart',
        immediate: true,
    },

    stream: {
        type: 'stream',
        op: 'update',
        name: 'devel',
        property: 'color',
        value: 'blue',
    },

    subscription__add: {
        type: 'subscription',
        op: 'add',
        subscriptions: [
            {
                name: 'devel',
                stream_id: 42,
                // etc.
            },
        ],
    },

    subscription__remove: {
        type: 'subscription',
        op: 'remove',
        subscriptions: [
            {
                stream_id: 42,
            },
        ],
    },

    subscription__peer_add: {
        type: 'subscription',
        op: 'peer_add',
        user_id: 555,
        subscriptions: [
            {
                name: 'devel',
                stream_id: 42,
                // etc.
            },
        ],
    },

    subscription__peer_remove: {
        type: 'subscription',
        op: 'peer_remove',
        user_id: 555,
        subscriptions: [
            {
                stream_id: 42,
                // etc.
            },
        ],
    },

    subscription__update: {
        type: 'subscription',
        op: 'update',
        name: 'devel',
        property: 'color',
        value: 'black',
    },

    update_display_settings__default_language: {
        type: 'update_display_settings',
        setting_name: 'default_language',
        setting: 'fr',
    },

    update_display_settings__left_side_userlist: {
        type: 'update_display_settings',
        setting_name: 'left_side_userlist',
        setting: true,
    },

    update_display_settings__emoji_alt_code: {
        type: 'update_display_settings',
        setting_name: 'emoji_alt_code',
        setting: true,
    },

    update_display_settings__twenty_four_hour_time: {
        type: 'update_display_settings',
        setting_name: 'twenty_four_hour_time',
        setting: true,
    },

    update_global_notifications: {
        type: 'update_global_notifications',
        notification_name: 'enable_stream_sounds',
        setting: true,
    },

    update_message_flags__read: {
        type: 'update_message_flags',
        operation: 'add',
        flag: 'read',
        messages: [5, 999],
    },

    update_message_flags__starred: {
        type: 'update_message_flags',
        operation: 'add',
        flag: 'starred',
        messages: [7, 99],
    },
};

function assert_same(actual, expected) {
    // This helper prevents us from getting false positives
    // where actual and expected are both undefined.
    assert(expected);
    assert.deepEqual(actual, expected);
}

// TODO: move this into library
function capture_args(res, arg_names) {
    // This function returns a function that, when
    // arg_names are ['foo', 'bar'] sets res.foo
    // to the first arg passed in and res.bar to
    // the second args passed in.  (It's basically
    // a mock.)

    _.each(res, function (value, key) {
        delete res[key];
    });

    return function () {
        var my_arguments = _.clone(arguments);
        _.each(arg_names, function (name, i) {
            res[name] = my_arguments[i];
        });
        return true;
    };
}


// This test suite is different than most, because
// most modules we test are dependent on a few
// set of modules, and it's useful for tests to
// all share the same stubs.  For a dispatcher,
// we want a higher level of isolation between
// our tests, so we wrap them with a run() method.

var run = (function () {
    var wrapper = function (f) {
        // We only ever mock one function at a time,
        // so we can have a little helper.
        var args = {}; // for stubs to capture args
        function capture(names) {
            return capture_args(args, names);
        }

        var clobber_callbacks = [];

        var override = function (module, func_name, f) {
            var impl = {};
            impl[func_name] = f;
            set_global(module, impl);

            clobber_callbacks.push(function () {
                // If you get a failure from this, you probably just
                // need to have your test do its own overrides and
                // not cherry-pick off of the prior test's setup.
                set_global(module, 'UNCLEAN MODULE FROM PRIOR TEST');
            });
        };

        f(override, capture, args);

        _.each(clobber_callbacks, function (f) {
            f();
        });
    };

    return wrapper;
}());


run(function () {
    // alert_words
    var event = event_fixtures.alert_words;
    dispatch(event);
    assert_same(global.alert_words.words, ['fire', 'lunch']);

});

run(function (override) {
    // default_streams
    var event = event_fixtures.default_streams;
    override('admin', 'update_default_streams_table', noop);
    dispatch(event);
    assert_same(page_params.realm_default_streams, event.default_streams);

});

run(function (override, capture, args) {
    // message
    var event = event_fixtures.message;
    override('message_store', 'insert_new_messages', capture(['messages']));
    server_events._get_events_success([event]);
    dispatch(event);
    assert_same(args.messages[0].content, event.message.content);

});

run(function (override, capture, args) {
    // muted_topics
    var event = event_fixtures.muted_topics;
    override('muting_ui', 'handle_updates', capture(['muted_topics']));
    dispatch(event);
    assert_same(args.muted_topics, event.muted_topics);

});

run(function () {
    // pointer
    var event = event_fixtures.pointer;
    global.pointer.furthest_read = 0;
    global.pointer.server_furthest_read = 0;
    dispatch(event);
    assert_same(global.pointer.furthest_read, event.pointer);
    assert_same(global.pointer.server_furthest_read, event.pointer);

});

run(function (override, capture, args) {
    // presence
    var event = event_fixtures.presence;
    override('activity', 'set_user_status', capture(['email', 'presence', 'server_time']));
    dispatch(event);
    assert_same(args.email, 'alice@example.com');
    assert_same(args.presence, event.presence);
    assert_same(args.server_time, event.server_timestamp);

});

run(function (override) {
    // realm
    function test_realm_boolean(event, parameter_name) {
        page_params[parameter_name] = true;
        event = _.clone(event);
        event.value = false;
        dispatch(event);
        assert.equal(page_params[parameter_name], false);
        event = _.clone(event);
        event.value = true;
        dispatch(event);
        assert.equal(page_params[parameter_name], true);
    }

    var event = event_fixtures.realm__update__create_stream_by_admins_only;
    test_realm_boolean(event, 'realm_create_stream_by_admins_only');

    event = event_fixtures.realm__update__invite_by_admins_only;
    test_realm_boolean(event, 'realm_invite_by_admins_only');

    event = event_fixtures.realm__update__invite_required;
    test_realm_boolean(event, 'realm_invite_required');

    event = event_fixtures.realm__update__name;
    override('notifications', 'redraw_title', noop);
    dispatch(event);
    assert_same(page_params.realm_name, 'new_realm_name');

    event = event_fixtures.realm__update__restricted_to_domain;
    test_realm_boolean(event, 'realm_restricted_to_domain');

    event = event_fixtures.realm__update_dict__default;
    page_params.realm_allow_message_editing = false;
    page_params.realm_message_content_edit_limit_seconds = 0;
    dispatch(event);
    assert_same(page_params.realm_allow_message_editing, true);
    assert_same(page_params.realm_message_content_edit_limit_seconds, 5);

});

run(function (override, capture, args) {
    // realm_bot
    var event = event_fixtures.realm_bot__add;
    override('bot_data', 'add', capture(['bot']));
    dispatch(event);
    assert_same(args.bot, event.bot);

    event = event_fixtures.realm_bot__remove;
    override('bot_data', 'deactivate', capture(['email']));
    dispatch(event);
    assert_same(args.email, event.bot.email);

    event = event_fixtures.realm_bot__update;
    override('bot_data', 'update', capture(['email', 'bot']));
    override('admin', 'update_user_data', capture(['update_user_id', 'update_bot_data']));
    dispatch(event);
    assert_same(args.email, event.bot.email);
    assert_same(args.bot, event.bot);
    assert_same(args.update_user_id, event.bot.user_id);
    assert_same(args.update_bot_data, event.bot);

});

run(function (override, capture, args) {
    // realm_emoji
    var event = event_fixtures.realm_emoji;
    override('emoji', 'update_emojis', capture(['realm_emoji']));
    override('admin', 'populate_emoji', noop);
    dispatch(event);
    assert_same(args.realm_emoji, event.realm_emoji);

});

run(function (override) {
    // realm_filters
    var event = event_fixtures.realm_filters;
    page_params.realm_filters = [];
    override('admin', 'populate_filters', noop);
    dispatch(event);
    assert_same(page_params.realm_filters, event.realm_filters);

});

run(function (override, capture, args) {
    // realm_user
    var event = event_fixtures.realm_user__add;
    override('people', 'add_in_realm', capture(['person']));
    dispatch(event);
    assert_same(args.person, event.person);

    event = event_fixtures.realm_user__remove;
    override('people', 'deactivate', capture(['person']));
    dispatch(event);
    assert_same(args.person, event.person);

    event = event_fixtures.realm_user__update;
    override('user_events', 'update_person', capture(['person']));
    dispatch(event);
    assert_same(args.person, event.person);

});

run(function (override, capture, args) {
    // referral
    var event = event_fixtures.referral;
    override('referral', 'update_state', capture(['granted', 'used']));
    dispatch(event);
    assert_same(args.granted, event.referrals.granted);
    assert_same(args.used, event.referrals.used);

});

run(function (override, capture, args) {
    // restart
    var event = event_fixtures.restart;
    override('reload', 'initiate', capture(['options']));
    dispatch(event);
    assert.equal(args.options.save_pointer, true);
    assert.equal(args.options.immediate, true);
});

run(function (override, capture, args) {
    // stream
    var event = event_fixtures.stream;

    override(
        'subs',
        'update_subscription_properties',
        capture(['name', 'property', 'value']));
    override('admin', 'update_default_streams_table', noop);
    dispatch(event);
    assert_same(args.name, event.name);
    assert_same(args.property, event.property);
    assert_same(args.value, event.value);

});

run(function (override, capture, args) {
    // subscription

    // This next section can go away when we start handling
    // user_ids more directly in some of subscriptions code.
    override('people', 'get_person_from_user_id', function (user_id) {
        assert_same(user_id, 555);
        return {email: 'this-is-not-really-used-in-the-test'};
    });

    var event = event_fixtures.subscription__add;
    override('subs', 'mark_subscribed', capture(['name', 'sub']));
    dispatch(event);
    assert_same(args.name, 'devel');
    assert_same(args.sub, event.subscriptions[0]);

    event = event_fixtures.subscription__peer_add;
    override('stream_data', 'add_subscriber', capture(['sub', 'user_id']));
    dispatch(event);
    assert_same(args.sub, event.subscriptions[0]);
    assert_same(args.user_id, 555);

    event = event_fixtures.subscription__peer_remove;
    override('stream_data', 'remove_subscriber', capture(['sub', 'user_id']));
    dispatch(event);
    assert_same(args.sub, event.subscriptions[0]);
    assert_same(args.user_id, 555);

    event = event_fixtures.subscription__remove;
    var stream_id_looked_up;
    var sub_stub = 'stub';
    override('stream_data', 'get_sub_by_id', function (stream_id) {
        stream_id_looked_up = stream_id;
        return sub_stub;
    });
    override('subs', 'mark_sub_unsubscribed', capture(['sub']));
    dispatch(event);
    assert_same(stream_id_looked_up, event.subscriptions[0].stream_id);
    assert_same(args.sub, sub_stub);

    event = event_fixtures.subscription__update;
    override(
        'subs',
        'update_subscription_properties',
        capture(['name', 'property', 'value']));
    dispatch(event);
    assert_same(args.name, event.name);
    assert_same(args.property, event.property);
    assert_same(args.value, event.value);

});

run(function (override) {
    // update_display_settings
    var event = event_fixtures.update_display_settings__default_language;
    page_params.default_language = 'en';
    dispatch(event);
    assert_same(page_params.default_language, 'fr');

    event = event_fixtures.update_display_settings__left_side_userlist;
    page_params.left_side_userlist = false;
    dispatch(event);
    assert_same(page_params.left_side_userlist, true);

    override('message_list', 'narrowed', noop);
    event = event_fixtures.update_display_settings__twenty_four_hour_time;
    page_params.twenty_four_hour_time = false;
    dispatch(event);
    assert_same(page_params.twenty_four_hour_time, true);

    event = event_fixtures.update_display_settings__emoji_alt_code;
    page_params.emoji_alt_code = false;
    dispatch(event);
    assert_same(page_params.emoji_alt_code, true);

});

run(function (override, capture, args) {
    // update_global_notifications
    var event = event_fixtures.update_global_notifications;
    override(
        'notifications',
        'handle_global_notification_updates',
        capture(['name', 'setting']));
    dispatch(event);
    assert_same(args.name, event.notification_name);
    assert_same(args.setting, event.setting);

});

run(function (override, capture, args) {
    // update_message_flags__read
    var event = event_fixtures.update_message_flags__read;
    override('message_store', 'get', capture(['message_id']));
    override('unread_ui', 'mark_messages_as_read', noop);
    dispatch(event);
    assert_same(args.message_id, 999);
});

run(function (override, capture, args) {
    // update_message_flags__starred
    var event = event_fixtures.update_message_flags__starred;
    override('ui', 'update_starred', capture(['message_id', 'new_value']));
    dispatch(event);
    assert_same(args.message_id, 99);
    assert_same(args.new_value, true); // for 'add'
});
