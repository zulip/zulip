var noop = function () {};

set_global('document', 'document-stub');
set_global('window', {});
set_global('$', function () {
    return {
        trigger: noop,
    };
});

// These dependencies are closer to the dispatcher, and they
// apply to all tests.
set_global('home_msg_list', {
    rerender: noop,
    select_id: noop,
    selected_id: function () {return 1;},
});
set_global('echo', {
    process_from_server: function (messages) {
        return messages;
    },
});

set_global('markdown', {
    set_realm_filters: noop,
});

set_global('notifications', {
    redraw_title: noop,
});

set_global('settings_emoji', {
    update_custom_emoji_ui: noop,
});

set_global('settings_account', {
    update_email_change_display: noop,
    update_name_change_display: noop,
});
set_global('settings_display', {
    update_page: noop,
});

set_global('settings_notifications', {
    update_page: noop,
});

set_global('settings_org', {
    sync_realm_settings: noop,
});

set_global('message_edit', {
    update_message_topic_editing_pencil: noop,
});

set_global('settings_bots', {
    update_bot_permissions_ui: noop,
});

// page_params is highly coupled to dispatching now
set_global('page_params', {test_suite: false});
var page_params = global.page_params;

// alert_words is coupled to dispatching in the sense
// that we write directly to alert_words.words
zrequire('alert_words');

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

zrequire('server_events_dispatch');
var sed = server_events_dispatch;

function dispatch(ev) {
    sed.dispatch_normal_event(ev);
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

    hotspots: {
        type: 'hotspots',
        hotspots: ['nice', 'chicken'],
    },

    muted_topics: {
        type: 'muted_topics',
        muted_topics: [['devel', 'js'], ['lunch', 'burritos']],
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

    reaction__add: {
        type: 'reaction',
        op: 'add',
        message_id: 128,
        emoji_name: 'anguished_pig',
        user: {
            id: "1",
        },
    },

    reaction__remove: {
        type: 'reaction',
        op: 'remove',
        message_id: 256,
        emoji_name: 'angery',
        user: {
            id: "1",
        },
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

    realm__update__bot_creation_policy: {
        type: 'realm',
        op: 'update',
        property: 'bot_creation_policy',
        value: 1,
    },

    realm__update__disallow_disposable_email_addresses: {
        type: 'realm',
        op: 'update',
        property: 'disallow_disposable_email_addresses',
        value: false,
    },

    realm__update_default_twenty_four_hour_time: {
        type: 'realm',
        op: 'update',
        property: 'default_twenty_four_hour_time',
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
            user_id: '42',
            full_name: 'The Bot',
        },
    },

    realm_bot__delete: {
        type: 'realm_bot',
        op: 'delete',
        bot: {
            email: 'the-bot@example.com',
            user_id: '42',
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

    realm_domains__add: {
        type: 'realm_domains',
        op: 'add',
        realm_domain: {
            domain: 'ramen',
            allow_subdomains: false,
        },
    },

    realm_domains__change: {
        type: 'realm_domains',
        op: 'change',
        realm_domain: {
            domain: 'ramen',
            allow_subdomains: true,
        },
    },

    realm_domains__remove: {
        type: 'realm_domains',
        op: 'remove',
        domain: 'ramen',
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
                email_address: 'devel+0138515295f4@zulipdev.com:9991',
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

    typing__start: {
        type: 'typing',
        sender: {
            user_id: 4,
        },
        op: 'start',
    },

    typing__stop: {
        type: 'typing',
        sender: {
            user_id: 6,
        },
        op: 'stop',
    },

    update_display_settings__default_language: {
        type: 'update_display_settings',
        setting_name: 'default_language',
        setting: 'fr',
        language_name: 'French',
    },

    update_display_settings__left_side_userlist: {
        type: 'update_display_settings',
        setting_name: 'left_side_userlist',
        setting: true,
    },

    update_display_settings__twenty_four_hour_time: {
        type: 'update_display_settings',
        setting_name: 'twenty_four_hour_time',
        setting: true,
    },

    update_display_settings__high_contrast_mode: {
        type: 'update_display_settings',
        setting_name: 'high_contrast_mode',
        setting: true,
    },

    update_display_settings__translate_emoticons: {
        type: 'update_display_settings',
        setting_name: 'translate_emoticons',
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

    delete_message: {
        type: 'delete_message',
        message_id: 1337,
        message_type: "stream",
        stream_id: 99,
        topic: 'topic1',
    },

    custom_profile_fields: {
        type: 'custom_profile_fields',
        fields: [
            {id: 1, name: 'teams', type: 1},
            {id: 2, name: 'hobbies', type: 1},
        ],
    },
};

function assert_same(actual, expected) {
    // This helper prevents us from getting false positives
    // where actual and expected are both undefined.
    assert(expected);
    assert.deepEqual(actual, expected);
}

var with_overrides = global.with_overrides; // make lint happy

with_overrides(function (override) {
    // alert_words
    override('alert_words_ui.render_alert_words_ui', noop);
    var event = event_fixtures.alert_words;
    dispatch(event);
    assert_same(global.alert_words.words, ['fire', 'lunch']);

});

with_overrides(function (override) {
    // custom profile fields
    var event = event_fixtures.custom_profile_fields;
    override('settings_profile_fields.populate_profile_fields', noop);
    override('settings_profile_fields.report_success', noop);
    dispatch(event);
    assert_same(global.page_params.custom_profile_fields, event.fields);

});

with_overrides(function (override) {
    // default_streams
    var event = event_fixtures.default_streams;
    override('settings_streams.update_default_streams_table', noop);
    global.with_stub(function (stub) {
        override('stream_data.set_realm_default_streams', stub.f);
        dispatch(event);
        var args = stub.get_args('realm_default_streams');
        assert_same(args.realm_default_streams, event.default_streams);
    });

});

with_overrides(function (override) {
    // hotspots
    var event = event_fixtures.hotspots;
    override('hotspots.load_new', noop);
    dispatch(event);
    assert_same(page_params.hotspots, event.hotspots);
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
    // reaction
    var event = event_fixtures.reaction__add;
    global.with_stub(function (stub) {
        override('reactions.add_reaction', stub.f);
        dispatch(event);
        var args = stub.get_args('event');
        assert_same(args.event.emoji_name, event.emoji_name);
        assert_same(args.event.message_id, event.message_id);
    });

    event = event_fixtures.reaction__remove;
    global.with_stub(function (stub) {
        override('reactions.remove_reaction', stub.f);
        dispatch(event);
        var args = stub.get_args('event');
        assert_same(args.event.emoji_name, event.emoji_name);
        assert_same(args.event.message_id, event.message_id);
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

    event = event_fixtures.realm__update__disallow_disposable_email_addresses;
    test_realm_boolean(event, 'realm_disallow_disposable_email_addresses');

    event = event_fixtures.realm__update__create_stream_by_admins_only;
    test_realm_boolean(event, 'realm_create_stream_by_admins_only');

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
    global.with_stub(function (bot_stub) {
        global.with_stub(function (admin_stub) {
            override('bot_data.add', bot_stub.f);
            override('settings_users.update_user_data', admin_stub.f);
            dispatch(event);
            var args = bot_stub.get_args('bot');
            assert_same(args.bot, event.bot);

            admin_stub.get_args('update_user_id', 'update_bot_data');
        });
    });

    event = event_fixtures.realm_bot__remove;
    global.with_stub(function (bot_stub) {
        global.with_stub(function (admin_stub) {
            override('bot_data.deactivate', bot_stub.f);
            override('settings_users.update_user_data', admin_stub.f);
            dispatch(event);
            var args = bot_stub.get_args('user_id');
            assert_same(args.user_id, event.bot.user_id);

            admin_stub.get_args('update_user_id', 'update_bot_data');
        });
    });

    event = event_fixtures.realm_bot__delete;
    global.with_stub(function (bot_stub) {
        global.with_stub(function (admin_stub) {
            override('bot_data.delete', bot_stub.f);
            override('settings_users.update_user_data', admin_stub.f);
            dispatch(event);
            var args = bot_stub.get_args('bot_id');
            assert_same(args.bot_id, event.bot.user_id);

            admin_stub.get_args('update_user_id', 'update_bot_data');
        });
    });

    event = event_fixtures.realm_bot__update;
    global.with_stub(function (bot_stub) {
        global.with_stub(function (admin_stub) {
            override('bot_data.update', bot_stub.f);
            override('settings_users.update_user_data', admin_stub.f);

            dispatch(event);

            var args = bot_stub.get_args('user_id', 'bot');
            assert_same(args.user_id, event.bot.user_id);
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
        override('settings_emoji.populate_emoji', noop);
        override('emoji_picker.generate_emoji_picker_data', noop);
        dispatch(event);
        var args = stub.get_args('realm_emoji');
        assert_same(args.realm_emoji, event.realm_emoji);
    });
});

with_overrides(function (override) {
    // realm_filters
    var event = event_fixtures.realm_filters;
    page_params.realm_filters = [];
    override('settings_filters.populate_filters', noop);
    dispatch(event);
    assert_same(page_params.realm_filters, event.realm_filters);

});

with_overrides(function (override) {
    // realm_domains
    var event = event_fixtures.realm_domains__add;
    page_params.realm_domains = [];
    override('settings_org.populate_realm_domains', noop);
    dispatch(event);
    assert_same(page_params.realm_domains, [event.realm_domain]);

    event = event_fixtures.realm_domains__change;
    dispatch(event);
    assert_same(page_params.realm_domains, [event.realm_domain]);

    event = event_fixtures.realm_domains__remove;
    dispatch(event);
    assert_same(page_params.realm_domains, []);
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
        override('stream_data.remove_deactivated_user_from_all_streams', noop);
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
        override('stream_events.update_property', stub.f);
        override('settings_streams.update_default_streams_table', noop);
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
    global.with_stub(function (subscription_stub) {
        global.with_stub(function (stream_email_stub) {
            override('stream_data.get_sub_by_id', function (stream_id) {
                return {stream_id: stream_id};
            });
            override('stream_events.mark_subscribed', subscription_stub.f);
            override('stream_data.update_stream_email_address', stream_email_stub.f);
            dispatch(event);
            var args = subscription_stub.get_args('sub', 'subscribers');
            assert_same(args.sub.stream_id, event.subscriptions[0].stream_id);
            assert_same(args.subscribers, event.subscriptions[0].subscribers);
            args = stream_email_stub.get_args('sub', 'email_address');
            assert_same(args.email_address, event.subscriptions[0].email_address);
            assert_same(args.sub.stream_id, event.subscriptions[0].stream_id);
        });
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
        override('stream_events.mark_unsubscribed', stub.f);
        dispatch(event);
        var args = stub.get_args('sub');
        assert_same(stream_id_looked_up, event.subscriptions[0].stream_id);
        assert_same(args.sub, sub_stub);
    });

    event = event_fixtures.subscription__update;
    global.with_stub(function (stub) {
        override('stream_events.update_property', stub.f);
        dispatch(event);
        var args = stub.get_args('stream_id', 'property', 'value');
        assert_same(args.stream_id, event.stream_id);
        assert_same(args.property, event.property);
        assert_same(args.value, event.value);
    });
});

with_overrides(function (override) {
    // typing
    var event = event_fixtures.typing__start;
    global.with_stub(function (stub) {
        override('typing_events.display_notification', stub.f);
        dispatch(event);
        var args = stub.get_args('event');
        assert_same(args.event.sender.user_id, 4);
    });

    event = event_fixtures.typing__stop;
    global.with_stub(function (stub) {
        override('typing_events.hide_notification', stub.f);
        dispatch(event);
        var args = stub.get_args('event');
        assert_same(args.event.sender.user_id, 6);
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

    event = event_fixtures.update_display_settings__translate_emoticons;
    page_params.translate_emoticons = false;
    dispatch(event);
    assert_same(page_params.translate_emoticons, true);
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

    global.with_stub(function (stub) {
        override('unread_ops.process_read_messages_event', stub.f);
        dispatch(event);
        var args = stub.get_args('message_ids');
        assert_same(args.message_ids, [999]);
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

// notify_server_message_read requires message_store and these dependencies.
zrequire('unread_ops');
zrequire('unread');
zrequire('topic_data');
zrequire('stream_list');
set_global('message_store', {});

with_overrides(function (override) {
    // delete_message
    var event = event_fixtures.delete_message;

    override('stream_list.update_streams_sidebar', noop);
    global.with_stub(function (stub) {
        override('ui.remove_message', stub.f);
        dispatch(event);
        var args = stub.get_args('message_id');
        assert_same(args.message_id, 1337);
    });
    global.with_stub(function (stub) {
        override('unread_ops.process_read_messages_event', stub.f);
        dispatch(event);
        var args = stub.get_args('message_ids');
        assert_same(args.message_ids, [1337]);
    });
    global.with_stub(function (stub) {
        override('topic_data.remove_message', stub.f);
        dispatch(event);
        var args = stub.get_args('opts');
        assert_same(args.opts.stream_id, 99);
        assert_same(args.opts.topic_name, 'topic1');
    });
});
