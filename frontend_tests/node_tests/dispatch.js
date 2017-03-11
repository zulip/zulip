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

// We use blueslip to print the traceback
set_global('blueslip', {
    error: function (msg, more_info, stack) {
        console.log("\nFailed to process an event:\n", more_info.event, "\n");
        var error = new Error();
        error.stack = stack;
        throw error;
    },
    exception_msg: function (ex) {
        return ex.message;
    },
});

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
        stream_id: 99,
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
                subscribers: ['alice@example.com', 'bob@example.com'],
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
        stream_id: 43,
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
        messages: [999],
    },

    update_message_flags__starred: {
        type: 'update_message_flags',
        operation: 'add',
        flag: 'starred',
        messages: [99],
    },
};

function assert_same(actual, expected) {
    // This helper prevents us from getting false positives
    // where actual and expected are both undefined.
    assert(expected);
    assert.deepEqual(actual, expected);
}

var with_overrides = global.with_overrides; // make lint happy

with_overrides(function () {
    // alert_words
    var event = event_fixtures.alert_words;
    dispatch(event);
    assert_same(global.alert_words.words, ['fire', 'lunch']);

});

with_overrides(function (override) {
    // default_streams
    var event = event_fixtures.default_streams;
    override('admin.update_default_streams_table', noop);
    dispatch(event);
    assert_same(page_params.realm_default_streams, event.default_streams);

});

with_overrides(function (override) {
    // message
    var event = event_fixtures.message;

    global.with_stub(function (stub) {
        override('message_store.insert_new_messages', stub.f);
        dispatch(event);
        var args = stub.get_args('messages');
        assert_same(args.messages[0].content, event.message.content);
    });
});

with_overrides(function (override) {
    // muted_topics
    var event = event_fixtures.muted_topics;

    global.with_stub(function (stub) {
        override('muting_ui.handle_updates', stub.f);
        dispatch(event);
        var args = stub.get_args('muted_topics');
        assert_same(args.muted_topics, event.muted_topics);
    });
});

with_overrides(function () {
    // pointer
    var event = event_fixtures.pointer;
    global.pointer.furthest_read = 0;
    global.pointer.server_furthest_read = 0;
    dispatch(event);
    assert_same(global.pointer.furthest_read, event.pointer);
    assert_same(global.pointer.server_furthest_read, event.pointer);

});

with_overrides(function (override) {
    // presence
    var event = event_fixtures.presence;

    global.with_stub(function (stub) {
        override('activity.set_user_status', stub.f);
        dispatch(event);
        var args = stub.get_args('email', 'presence', 'server_time');
        assert_same(args.email, 'alice@example.com');
        assert_same(args.presence, event.presence);
        assert_same(args.server_time, event.server_timestamp);
    });
});

with_overrides(function (override) {
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
    override('notifications.redraw_title', noop);
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

with_overrides(function (override) {
    // realm_bot
    var event = event_fixtures.realm_bot__add;
    global.with_stub(function (stub) {
        override('bot_data.add', stub.f);
        dispatch(event);
        var args = stub.get_args('bot');
        assert_same(args.bot, event.bot);
    });

    event = event_fixtures.realm_bot__remove;
    global.with_stub(function (stub) {
        override('bot_data.deactivate', stub.f);
        dispatch(event);
        var args = stub.get_args('email');
        assert_same(args.email, event.bot.email);
    });

    event = event_fixtures.realm_bot__update;
    global.with_stub(function (bot_stub) {
        global.with_stub(function (admin_stub) {
            override('bot_data.update', bot_stub.f);
            override('admin.update_user_data', admin_stub.f);

            dispatch(event);

            var args = bot_stub.get_args('email', 'bot');
            assert_same(args.email, event.bot.email);
            assert_same(args.bot, event.bot);

            args = admin_stub.get_args('update_user_id', 'update_bot_data');
            assert_same(args.update_user_id, event.bot.user_id);
            assert_same(args.update_bot_data, event.bot);
        });
    });
});

with_overrides(function (override) {
    // realm_emoji
    var event = event_fixtures.realm_emoji;

    global.with_stub(function (stub) {
        override('emoji.update_emojis', stub.f);
        override('admin.populate_emoji', noop);
        dispatch(event);
        var args = stub.get_args('realm_emoji');
        assert_same(args.realm_emoji, event.realm_emoji);
    });
});

with_overrides(function (override) {
    // realm_filters
    var event = event_fixtures.realm_filters;
    page_params.realm_filters = [];
    override('admin.populate_filters', noop);
    dispatch(event);
    assert_same(page_params.realm_filters, event.realm_filters);

});

with_overrides(function (override) {
    // realm_user
    var event = event_fixtures.realm_user__add;
    global.with_stub(function (stub) {
        override('people.add_in_realm', stub.f);
        dispatch(event);
        var args = stub.get_args('person');
        assert_same(args.person, event.person);
    });

    event = event_fixtures.realm_user__remove;
    global.with_stub(function (stub) {
        override('people.deactivate', stub.f);
        dispatch(event);
        var args = stub.get_args('person');
        assert_same(args.person, event.person);
    });

    event = event_fixtures.realm_user__update;
    global.with_stub(function (stub) {
        override('user_events.update_person', stub.f);
        dispatch(event);
        var args = stub.get_args('person');
        assert_same(args.person, event.person);
    });
});

with_overrides(function (override) {
    // referral
    var event = event_fixtures.referral;
    global.with_stub(function (stub) {
        override('referral.update_state', stub.f);
        dispatch(event);
        var args = stub.get_args('granted', 'used');
        assert_same(args.granted, event.referrals.granted);
        assert_same(args.used, event.referrals.used);
    });
});

with_overrides(function (override) {
    // restart
    var event = event_fixtures.restart;
    global.with_stub(function (stub) {
        override('reload.initiate', stub.f);
        dispatch(event);
        var args = stub.get_args('options');
        assert.equal(args.options.save_pointer, true);
        assert.equal(args.options.immediate, true);
    });
});

with_overrides(function (override) {
    // stream
    var event = event_fixtures.stream;

    global.with_stub(function (stub) {
        override('subs.update_subscription_properties', stub.f);
        override('admin.update_default_streams_table', noop);
        dispatch(event);
        var args = stub.get_args('stream_id', 'property', 'value');
        assert_same(args.stream_id, event.stream_id);
        assert_same(args.property, event.property);
        assert_same(args.value, event.value);
    });
});

with_overrides(function (override) {
    // subscription

    // This next section can go away when we start handling
    // user_ids more directly in some of subscriptions code.
    override('people.get_person_from_user_id', function (user_id) {
        assert_same(user_id, 555);
        return {email: 'this-is-not-really-used-in-the-test'};
    });

    var event = event_fixtures.subscription__add;
    global.with_stub(function (stub) {
        override('stream_data.get_sub_by_id', function (stream_id) {
            return {stream_id: stream_id};
        });
        override('subs.mark_subscribed', stub.f);
        dispatch(event);
        var args = stub.get_args('sub', 'subscribers');
        assert_same(args.sub.stream_id, event.subscriptions[0].stream_id);
        assert_same(args.subscribers, event.subscriptions[0].subscribers);
    });

    event = event_fixtures.subscription__peer_add;
    global.with_stub(function (stub) {
        override('stream_data.add_subscriber', stub.f);
        dispatch(event);
        var args = stub.get_args('sub', 'user_id');
        assert_same(args.sub, event.subscriptions[0]);
        assert_same(args.user_id, 555);
    });

    event = event_fixtures.subscription__peer_remove;
    global.with_stub(function (stub) {
        override('stream_data.remove_subscriber', stub.f);
        dispatch(event);
        var args = stub.get_args('sub', 'user_id');
        assert_same(args.sub, event.subscriptions[0]);
        assert_same(args.user_id, 555);
    });

    event = event_fixtures.subscription__remove;
    var stream_id_looked_up;
    var sub_stub = 'stub';
    override('stream_data.get_sub_by_id', function (stream_id) {
        stream_id_looked_up = stream_id;
        return sub_stub;
    });
    global.with_stub(function (stub) {
        override('subs.mark_sub_unsubscribed', stub.f);
        dispatch(event);
        var args = stub.get_args('sub');
        assert_same(stream_id_looked_up, event.subscriptions[0].stream_id);
        assert_same(args.sub, sub_stub);
    });

    event = event_fixtures.subscription__update;
    global.with_stub(function (stub) {
        override('subs.update_subscription_properties', stub.f);
        dispatch(event);
        var args = stub.get_args('stream_id', 'property', 'value');
        assert_same(args.stream_id, event.stream_id);
        assert_same(args.property, event.property);
        assert_same(args.value, event.value);
    });
});

with_overrides(function (override) {
    // update_display_settings
    var event = event_fixtures.update_display_settings__default_language;
    page_params.default_language = 'en';
    dispatch(event);
    assert_same(page_params.default_language, 'fr');

    event = event_fixtures.update_display_settings__left_side_userlist;
    page_params.left_side_userlist = false;
    dispatch(event);
    assert_same(page_params.left_side_userlist, true);

    override('message_list.narrowed', noop);
    event = event_fixtures.update_display_settings__twenty_four_hour_time;
    page_params.twenty_four_hour_time = false;
    dispatch(event);
    assert_same(page_params.twenty_four_hour_time, true);

    event = event_fixtures.update_display_settings__emoji_alt_code;
    page_params.emoji_alt_code = false;
    dispatch(event);
    assert_same(page_params.emoji_alt_code, true);

});

with_overrides(function (override) {
    // update_global_notifications
    var event = event_fixtures.update_global_notifications;
    global.with_stub(function (stub) {
        override('notifications.handle_global_notification_updates', stub.f);
        dispatch(event);
        var args = stub.get_args('name', 'setting');
        assert_same(args.name, event.notification_name);
        assert_same(args.setting, event.setting);
    });
});

with_overrides(function (override) {
    // update_message_flags__read
    var event = event_fixtures.update_message_flags__read;
    override('unread_ui.mark_messages_as_read', noop);

    global.with_stub(function (stub) {
        override('message_store.get', stub.f);
        dispatch(event);
        var args = stub.get_args('message_id');
        assert_same(args.message_id, 999);
    });
});

with_overrides(function (override) {
    // update_message_flags__starred
    var event = event_fixtures.update_message_flags__starred;
    global.with_stub(function (stub) {
        override('ui.update_starred', stub.f);
        dispatch(event);
        var args = stub.get_args('message_id', 'new_value');
        assert_same(args.message_id, 99);
        assert_same(args.new_value, true); // for 'add'
    });
});
