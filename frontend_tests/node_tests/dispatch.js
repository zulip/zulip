var noop = function () {};

set_global('document', 'document-stub');
set_global('$', global.make_zjquery());

global.patch_builtin('window', {});
global.patch_builtin('setTimeout', func => func());

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
    add_custom_profile_fields_to_settings: noop,
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

// notify_server_message_read requires message_store and these dependencies.
zrequire('unread');
zrequire('topic_data');
zrequire('stream_list');
zrequire('message_flags');
zrequire('message_store');
zrequire('people');
zrequire('starred_messages');
zrequire('util');
zrequire('user_status');
zrequire('server_events_dispatch');

function dispatch(ev) {
    server_events_dispatch.dispatch_normal_event(ev);
}

var test_user = {
    email: 'test@example.com',
    user_id: 101,
    full_name: 'Test User',
};

people.init();
people.add(test_user);

var test_message = {
    sender_id: test_user.user_id,
    id: 99,
};
message_store.add_message_metadata(test_message);

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

    attachment: {
        type: 'attachment',
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

    invites_changed: {
        type: 'invites_changed',
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

    realm__update__emails_restricted_to_domains: {
        type: 'realm',
        op: 'update',
        property: 'emails_restricted_to_domains',
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

    realm__update_notifications_stream_id: {
        type: 'realm',
        op: 'update',
        property: 'notifications_stream_id',
        value: 42,
    },

    realm__update_signup_notifications_stream_id: {
        type: 'realm',
        op: 'update',
        property: 'signup_notifications_stream_id',
        value: 41,
    },

    realm__update_dict__default: {
        type: 'realm',
        op: 'update_dict',
        property: 'default',
        data: {
            allow_message_editing: true,
            message_content_edit_limit_seconds: 5,
            authentication_methods: {
                Google: true,
            },
        },
    },

    realm__update_dict__icon: {
        type: 'realm',
        op: 'update_dict',
        property: 'icon',
        data: {
            icon_url: 'icon.png',
            icon_source: 'U',
        },
    },

    realm__update_dict__logo: {
        type: 'realm',
        op: 'update_dict',
        property: 'logo',
        data: {
            logo_url: 'logo.png',
            logo_source: 'U',
        },
    },

    realm__update_dict__night_logo: {
        type: 'realm',
        op: 'update_dict',
        property: 'night_logo',
        data: {
            night_logo_url: 'night_logo.png',
            night_logo_source: 'U',
        },
    },

    realm__deactivated: {
        type: 'realm',
        op: 'deactivated',
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

    realm_bot__update_owner: {
        type: 'realm_bot',
        op: 'update',
        bot: {
            email: 'the-bot@example.com',
            user_id: 4321,
            full_name: 'The Bot Has A New Name',
            owner_id: test_user.user_id,
        },
    },

    realm_emoji: {
        type: 'realm_emoji',
        realm_emoji: {
            airplane: {
                source_url: 'some_url',
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
            email: 'added@example.com',
            full_name: 'Added Person',
            user_id: 1001,
        },
    },

    realm_user__remove: {
        type: 'realm_user',
        op: 'remove',
        person: {
            email: 'added@example.com',
            user_id: 1001,
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

    stream__update: {
        type: 'stream',
        op: 'update',
        name: 'devel',
        stream_id: 99,
        property: 'color',
        value: 'blue',
    },

    stream__create: {
        type: 'stream',
        op: 'create',
        streams: [
            {stream_id: 42},
            {stream_id: 99},
        ],
    },

    stream__delete: {
        type: 'stream',
        op: 'delete',
        streams: [
            {stream_id: 42},
            {stream_id: 99},
        ],
    },

    submessage: {
        type: 'submessage',
        submessage_id: 99,
        sender_id: 42,
        msg_type: 'stream',
        message_id: 56,
        content: 'test',
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

    typing__self: {
        type: 'typing',
        sender: {
            user_id: 5,
        },
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

    update_display_settings__dense_mode: {
        type: 'update_display_settings',
        setting_name: 'dense_mode',
        setting: true,
    },

    update_display_settings__night_mode: {
        type: 'update_display_settings',
        setting_name: 'night_mode',
        setting: true,
    },

    update_display_settings__night_mode_false: {
        type: 'update_display_settings',
        setting_name: 'night_mode',
        setting: false,
    },

    update_display_settings__starred_message_counts: {
        type: 'update_display_settings',
        setting_name: 'starred_message_counts',
        setting: true,
    },

    update_display_settings__translate_emoticons: {
        type: 'update_display_settings',
        setting_name: 'translate_emoticons',
        setting: true,
    },

    update_display_settings__emojiset: {
        type: 'update_display_settings',
        setting_name: 'emojiset',
        setting: 'google',
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

    update_message_flags__starred_add: {
        type: 'update_message_flags',
        operation: 'add',
        flag: 'starred',
        messages: [test_message.id],
    },

    update_message_flags__starred_remove: {
        type: 'update_message_flags',
        operation: 'remove',
        flag: 'starred',
        messages: [test_message.id],
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
    user_group__add: {
        type: 'user_group',
        op: 'add',
        group: {
            name: 'Mobile',
            id: '1',
            members: [1],
        },
    },
    user_group__add_members: {
        type: 'user_group',
        op: 'add_members',
        group_id: 1,
        user_ids: [2],
    },
    user_group__remove_members: {
        type: 'user_group',
        op: 'remove_members',
        group_id: 3,
        user_ids: [99, 100],
    },
    user_group__update: {
        type: 'user_group',
        op: 'update',
        group_id: 3,
        data: {
            name: 'Frontend',
            description: 'All Frontend people',
        },
    },
    user_status__revoke_away: {
        type: 'user_status',
        user_id: 63,
        away: false,
    },
    user_status__set_away: {
        type: 'user_status',
        user_id: 55,
        away: true,
    },
    user_status__set_status_text: {
        type: 'user_status',
        user_id: test_user.user_id,
        status_text: 'out to lunch',
    },
};

function assert_same(actual, expected) {
    // This helper prevents us from getting false positives
    // where actual and expected are both undefined.
    assert(expected !== undefined);
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
    // attachements
    var event = event_fixtures.attachment;
    global.with_stub(function (stub) {
        override('attachments_ui.update_attachments', stub.f);
        dispatch(event);
        assert_same(stub.get_args('event').event, event);
    });
});

with_overrides(function (override) {
    // User groups
    var event = event_fixtures.user_group__add;
    override('settings_user_groups.reload', noop);
    global.with_stub(function (stub) {
        override('user_groups.add', stub.f);
        dispatch(event);
        var args = stub.get_args('group');
        assert_same(args.group, event.group);
    });

    event = event_fixtures.user_group__add_members;
    global.with_stub(function (stub) {
        override('user_groups.add_members', stub.f);
        dispatch(event);
        var args = stub.get_args('group_id', 'user_ids');
        assert_same(args.group_id, event.group_id);
        assert_same(args.user_ids, event.user_ids);
    });

    event = event_fixtures.user_group__remove_members;
    global.with_stub(function (stub) {
        override('user_groups.remove_members', stub.f);
        dispatch(event);
        var args = stub.get_args('group_id', 'user_ids');
        assert_same(args.group_id, event.group_id);
        assert_same(args.user_ids, event.user_ids);
    });

    event = event_fixtures.user_group__update;
    global.with_stub(function (stub) {
        override('user_groups.update', stub.f);
        dispatch(event);
        var args = stub.get_args('event');
        assert_same(args.event.group_id, event.group_id);
        assert_same(args.event.data.name, event.data.name);
        assert_same(args.event.data.description, event.data.description);
    });
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
    // invites_changed
    var event = event_fixtures.invites_changed;
    $('#admin-invites-list').length = 1;
    global.with_stub(function (stub) {
        override('settings_invites.set_up', stub.f);
        dispatch(event); // stub automatically checks if stub.f is called once
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

with_overrides(function (override) {
    // presence
    var event = event_fixtures.presence;

    global.with_stub(function (stub) {
        override('activity.update_presence_info', stub.f);
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
    dispatch(event);
    assert_same(page_params.realm_name, 'new_realm_name');

    var called = false;
    window.electron_bridge = {
        send_event: (key, val) => {
            assert_same(key, 'realm_name');
            assert_same(val, 'new_realm_name');
            called = true;
        },
    };

    dispatch(event);
    assert_same(called, true);

    event = event_fixtures.realm__update__emails_restricted_to_domains;
    test_realm_boolean(event, 'realm_emails_restricted_to_domains');

    event = event_fixtures.realm__update__disallow_disposable_email_addresses;
    test_realm_boolean(event, 'realm_disallow_disposable_email_addresses');

    event = event_fixtures.realm__update__create_stream_by_admins_only;
    test_realm_boolean(event, 'realm_create_stream_by_admins_only');

    event = event_fixtures.realm__update_notifications_stream_id;
    override('settings_org.render_notifications_stream_ui', noop);
    dispatch(event);
    assert_same(page_params.realm_notifications_stream_id, 42);
    page_params.realm_notifications_stream_id = -1;  // make sure to reset for future tests

    event = event_fixtures.realm__update_signup_notifications_stream_id;
    dispatch(event);
    assert_same(page_params.realm_signup_notifications_stream_id, 41);
    page_params.realm_signup_notifications_stream_id = -1; // make sure to reset for future tests

    event = event_fixtures.realm__update_dict__default;
    page_params.realm_allow_message_editing = false;
    page_params.realm_message_content_edit_limit_seconds = 0;
    override('settings_org.populate_auth_methods', noop);
    dispatch(event);
    assert_same(page_params.realm_allow_message_editing, true);
    assert_same(page_params.realm_message_content_edit_limit_seconds, 5);
    assert_same(page_params.realm_authentication_methods, {Google: true});

    event = event_fixtures.realm__update_dict__icon;
    override('realm_icon.rerender', noop);

    called = false;
    window.electron_bridge = {
        send_event: (key, val) => {
            assert_same(key, 'realm_icon_url');
            assert_same(val, 'icon.png');
            called = true;
        },
    };

    dispatch(event);

    assert_same(called, true);
    assert_same(page_params.realm_icon_url, 'icon.png');
    assert_same(page_params.realm_icon_source, 'U');

    event = event_fixtures.realm__update_dict__logo;
    override('realm_logo.rerender', noop);
    dispatch(event);
    assert_same(page_params.realm_logo_url, 'logo.png');
    assert_same(page_params.realm_logo_source, 'U');

    event = event_fixtures.realm__update_dict__night_logo;
    override('realm_logo.rerender', noop);
    dispatch(event);
    assert_same(page_params.realm_night_logo_url, 'night_logo.png');
    assert_same(page_params.realm_night_logo_source, 'U');

    event = event_fixtures.realm__deactivated;
    window.location = {};
    dispatch(event);
    assert_same(window.location.href, "/accounts/deactivated/");
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

    event = event_fixtures.realm_bot__update_owner;
    override('bot_data.update', noop);
    override('settings_users.update_user_data', noop);
    dispatch(event);
    assert_same(event.bot.owner, 'test@example.com');
});

with_overrides(function (override) {
    // realm_emoji
    var event = event_fixtures.realm_emoji;

    global.with_stub(function (stub) {
        override('emoji.update_emojis', stub.f);
        override('settings_emoji.populate_emoji', noop);
        override('emoji_picker.generate_emoji_picker_data', noop);
        override('composebox_typeahead.update_emoji_data', noop);
        dispatch(event);
        var args = stub.get_args('realm_emoji');
        assert_same(args.realm_emoji, event.realm_emoji);
    });
});

with_overrides(function (override) {
    // realm_filters
    var event = event_fixtures.realm_filters;
    page_params.realm_filters = [];
    override('settings_linkifiers.populate_filters', noop);
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
    dispatch(event);
    var added_person = people.get_person_from_user_id(event.person.user_id);
    assert.equal(added_person.full_name, 'Added Person');
    assert(people.is_active_user_for_popover(event.person.user_id));

    event = event_fixtures.realm_user__remove;
    override('stream_events.remove_deactivated_user_from_all_streams', noop);
    dispatch(event);

    // We don't actually remove the person, we just deactivate them.
    var removed_person = people.get_person_from_user_id(event.person.user_id);
    assert.equal(removed_person.full_name, 'Added Person');
    assert(!people.is_active_user_for_popover(event.person.user_id));

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
    // stream update
    var event = event_fixtures.stream__update;

    global.with_stub(function (stub) {
        override('stream_events.update_property', stub.f);
        override('settings_streams.update_default_streams_table', noop);
        dispatch(event);
        var args = stub.get_args('stream_id', 'property', 'value');
        assert_same(args.stream_id, event.stream_id);
        assert_same(args.property, event.property);
        assert_same(args.value, event.value);
    });

    // stream create
    event = event_fixtures.stream__create;
    global.with_stub(function (stub) {
        override('stream_data.create_streams', stub.f);
        override('stream_data.get_sub_by_id', noop);
        override('stream_data.update_calculated_fields', noop);
        override('subs.add_sub_to_table', noop);
        dispatch(event);
        var args = stub.get_args('streams');
        assert_same(_.pluck(args.streams, 'stream_id'), [42, 99]);
    });

    // stream delete
    event = event_fixtures.stream__delete;
    global.with_stub(function (stub) {
        override('subs.remove_stream', noop);
        override('stream_data.delete_sub', noop);
        override('settings_streams.remove_default_stream', noop);
        override('stream_data.remove_default_stream', noop);

        override('stream_data.get_sub_by_id', function (id) {
            return id === 42 ? {subscribed: true} : {subscribed: false};
        });
        override('stream_list.remove_sidebar_row', stub.f);
        dispatch(event);
        var args = stub.get_args('stream_id');
        assert_same(args.stream_id, 42);

        override('stream_list.remove_sidebar_row', noop);
        override('settings_org.render_notifications_stream_ui', noop);
        page_params.realm_notifications_stream_id = 42;
        dispatch(event);
        assert_same(page_params.realm_notifications_stream_id, -1);

        page_params.realm_signup_notifications_stream_id = 42;
        dispatch(event);
        assert_same(page_params.realm_signup_notifications_stream_id, -1);
    });
});

with_overrides(function (override) {
    // submessage
    var event = event_fixtures.submessage;
    global.with_stub(function (stub) {
        override('submessage.handle_event', stub.f);
        dispatch(event);
        var submsg = stub.get_args('submsg').submsg;
        assert_same(submsg, {
            id: 99,
            sender_id: 42,
            msg_type: 'stream',
            message_id: 56,
            content: 'test',
        });
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

    // test blueslip errors/warns
    event = event_fixtures.subscription__add;
    global.with_stub(function (stub) {
        override('stream_data.get_sub_by_id', noop);
        override('blueslip.error', stub.f);
        dispatch(event);
        assert_same(stub.get_args('param').param, 'Subscribing to unknown stream with ID 42');
    });

    event = event_fixtures.subscription__peer_add;
    global.with_stub(function (stub) {
        override('stream_data.add_subscriber', noop);
        override('blueslip.warn', stub.f);
        dispatch(event);
        assert_same(stub.get_args('param').param, 'Cannot process peer_add event');
    });

    event = event_fixtures.subscription__peer_remove;
    global.with_stub(function (stub) {
        override('stream_data.remove_subscriber', noop);
        override('blueslip.warn', stub.f);
        dispatch(event);
        assert_same(stub.get_args('param').param, 'Cannot process peer_remove event.');
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

    page_params.user_id = 5;
    event = event_fixtures.typing__self;
    dispatch(event); // get line coverage
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

    var called = false;
    current_msg_list.rerender = () => {
        called = true;
    };

    override('message_list.narrowed', current_msg_list);
    event = event_fixtures.update_display_settings__twenty_four_hour_time;
    page_params.twenty_four_hour_time = false;
    dispatch(event);
    assert_same(page_params.twenty_four_hour_time, true);
    assert_same(called, true);

    event = event_fixtures.update_display_settings__translate_emoticons;
    page_params.translate_emoticons = false;
    dispatch(event);
    assert_same(page_params.translate_emoticons, true);

    event = event_fixtures.update_display_settings__high_contrast_mode;
    page_params.high_contrast_mode = false;
    var toggled = [];
    $("body").toggleClass = (cls) => {
        toggled.push(cls);
    };
    dispatch(event);
    assert_same(page_params.high_contrast_mode, true);
    assert_same(toggled, ['high-contrast']);

    event = event_fixtures.update_display_settings__dense_mode;
    page_params.dense_mode = false;
    toggled = [];
    dispatch(event);
    assert_same(page_params.dense_mode, true);
    assert_same(toggled, ['less_dense_mode', 'more_dense_mode']);

    $("body").fadeOut = (secs) => { assert_same(secs, 300); };
    $("body").fadeIn  = (secs) => { assert_same(secs, 300); };

    global.with_stub(function (stub) {
        event = event_fixtures.update_display_settings__night_mode;
        page_params.night_mode = false;
        override('night_mode.enable', stub.f); // automatically checks if called
        override('realm_logo.rerender', noop);
        dispatch(event);
        assert_same(page_params.night_mode, true);
    });

    global.with_stub(function (stub) {
        event = event_fixtures.update_display_settings__night_mode_false;
        page_params.night_mode = true;
        override('night_mode.disable', stub.f); // automatically checks if called
        dispatch(event);
        assert(!page_params.night_mode);
    });

    global.with_stub(function (stub) {
        event = event_fixtures.update_display_settings__emojiset;
        called = false;
        override('settings_display.report_emojiset_change', stub.f);
        page_params.emojiset = 'text';
        dispatch(event);
        assert_same(called, true);
        assert_same(page_params.emojiset, 'google');
    });

    override('starred_messages.rerender_ui', noop);
    event = event_fixtures.update_display_settings__starred_message_counts;
    page_params.starred_message_counts = false;
    dispatch(event);
    assert_same(page_params.starred_message_counts, true);
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

    override('starred_messages.rerender_ui', noop);

    var event = event_fixtures.update_message_flags__starred_add;
    global.with_stub(function (stub) {
        override('ui.update_starred_view', stub.f);
        dispatch(event);
        var args = stub.get_args('message_id', 'new_value');
        assert_same(args.message_id, test_message.id);
        assert_same(args.new_value, true); // for 'add'
        var msg = message_store.get(test_message.id);
        assert.equal(msg.starred, true);
    });

    event = event_fixtures.update_message_flags__starred_remove;
    global.with_stub(function (stub) {
        override('ui.update_starred_view', stub.f);
        dispatch(event);
        var args = stub.get_args('message_id', 'new_value');
        assert_same(args.message_id, test_message.id);
        assert_same(args.new_value, false);
        var msg = message_store.get(test_message.id);
        assert.equal(msg.starred, false);
    });
});

with_overrides(function (override) {
    // delete_message
    var event = event_fixtures.delete_message;

    override('stream_list.update_streams_sidebar', noop);
    global.with_stub(function (stub) {
        override('unread_ops.process_read_messages_event', noop);
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

with_overrides(function (override) {
    // attachements
    var event = event_fixtures.user_status__set_away;
    global.with_stub(function (stub) {
        override('activity.on_set_away', stub.f);
        dispatch(event);
        var args = stub.get_args('user_id');
        assert_same(args.user_id, 55);
    });

    event = event_fixtures.user_status__revoke_away;
    global.with_stub(function (stub) {
        override('activity.on_revoke_away', stub.f);
        dispatch(event);
        var args = stub.get_args('user_id');
        assert_same(args.user_id, 63);
    });

    event = event_fixtures.user_status__set_status_text;
    global.with_stub(function (stub) {
        override('activity.redraw_user', stub.f);
        dispatch(event);
        var args = stub.get_args('user_id');
        assert_same(args.user_id, test_user.user_id);
        var status_text = user_status.get_status_text(test_user.user_id);
        assert.equal(status_text, 'out to lunch');
    });
});
