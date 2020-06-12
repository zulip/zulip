// TODO: These events are not guaranteed to be perfectly
//       representative of what the server sends.  For
//       now we just want very basic test coverage.  We
//       have more mature tests for events on the backend
//       side in test_events.py, and we may be able to
//       re-work both sides (js/python) so that we work off
//       a shared fixture.

exports.test_user = {
    email: 'test@example.com',
    user_id: 101,
    full_name: 'Test User',
};

exports.test_message = {
    sender_id: exports.test_user.user_id,
    id: 99,
};

exports.fixtures = {
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
        user_id: 42,
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
        user_id: "1",
        user: {
            id: "1",
        },
    },

    reaction__remove: {
        type: 'reaction',
        op: 'remove',
        message_id: 256,
        emoji_name: 'angery',
        user_id: "1",
        user: {
            id: "1",
        },
    },

    // Please keep this next section un-nested, as we want this to partly
    // be simple documentation on the formats of individual events.
    realm__update__create_stream_policy: {
        type: 'realm',
        op: 'update',
        property: 'create_stream_policy',
        value: 2,
    },

    realm__update__invite_to_stream_policy: {
        type: 'realm',
        op: 'update',
        property: 'invite_to_stream_policy',
        value: 2,
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

    realm__update__email_addresses_visibility: {
        type: 'realm',
        op: 'update',
        property: 'email_address_visibility',
        value: 3,
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

    realm__update_default_code_block_language: {
        type: 'realm',
        op: 'update',
        property: 'default_code_block_language',
        value: 'javascript',
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

    update_display_settings__fluid_layout_width: {
        type: 'update_display_settings',
        setting_name: 'fluid_layout_width',
        setting: true,
    },

    update_display_settings__demote_inactive_streams: {
        type: 'update_display_settings',
        setting_name: 'demote_inactive_streams',
        setting: 2,
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
        notification_name: 'enable_stream_audible_notifications',
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
        messages: [exports.test_message.id],
    },

    update_message_flags__starred_remove: {
        type: 'update_message_flags',
        operation: 'remove',
        flag: 'starred',
        messages: [exports.test_message.id],
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
        user_id: exports.test_user.user_id,
        status_text: 'out to lunch',
    },
    realm_export: {
        type: 'realm_export',
        exports: {
            acting_user_id: 55,
            event_time: 'noon',
            path: 'some_path',
        },
    },
};

