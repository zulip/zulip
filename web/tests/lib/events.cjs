"use strict";

//  These events are not guaranteed to be perfectly
//  representative of what the server sends.  We
//  have a tool called check-schemas that tries
//  to validate this data against server side schemas,
//  but there are certain edge cases that the tool now
//  skips.  And even when the data matches the schema,
//  it may not be completely representative.

const test_user = {
    email: "test@example.com",
    user_id: 101,
    full_name: "Test User",
};
exports.test_user = test_user;

exports.test_message = {
    sender_id: test_user.user_id,
    id: 99,
};

const typing_person1 = {
    user_id: 1,
    email: "user1@example.com",
};

const typing_person2 = {
    user_id: 2,
    email: "user2@example.com",
};

exports.typing_person1 = typing_person1;
exports.typing_person2 = typing_person2;
exports.stream_typing_in_id = 1;
exports.topic_typing_in = "Typing topic";

const fake_then = 1596710000;
const fake_now = 1596713966;

exports.test_streams = {
    devel: {
        is_archived: false,
        name: "devel",
        description: ":devel fun:",
        rendered_description: "<b>devel fun</b>",
        invite_only: false,
        stream_id: 101,
        date_created: fake_now,
        creator_id: null,
        first_message_id: 1,
        history_public_to_subscribers: false,
        is_announcement_only: false,
        is_web_public: false,
        message_retention_days: null,
        stream_post_policy: 1,
        topics_policy: "inherit",
        can_administer_channel_group: 2,
        can_move_messages_out_of_channel_group: 2,
        can_move_messages_within_channel_group: 2,
        can_send_message_group: 2,
        can_remove_subscribers_group: 2,
        is_recently_active: true,
    },
    test: {
        is_archived: false,
        name: "test",
        description: "test desc",
        rendered_description: "test desc",
        invite_only: true,
        stream_id: 102,
        date_created: fake_then,
        creator_id: null,
        first_message_id: 1,
        history_public_to_subscribers: false,
        is_web_public: false,
        is_announcement_only: false,
        message_retention_days: null,
        stream_post_policy: 1,
        topics_policy: "inherit",
        can_administer_channel_group: 2,
        can_move_messages_out_of_channel_group: 2,
        can_move_messages_within_channel_group: 2,
        can_send_message_group: 2,
        can_remove_subscribers_group: 2,
        is_recently_active: true,
    },
};

const streams = exports.test_streams;

// TODO: we want to validate this better with check-schema.
// The data should mostly be representative here, but we don't
// really exercise it in our tests yet.
const message_detail = {
    type: "stream",
    mentioned: false,
    sender_id: test_user.id,
    stream_id: streams.devel.test_id,
};

exports.test_realm_emojis = {
    101: {
        id: "101",
        name: "spain",
        source_url: "/some/path/to/spain.gif",
        still_url: "/some/path/to/spain.png",
        deactivated: false,
        author_id: test_user.user_id,
    },
    102: {
        id: "102",
        name: "green_tick",
        author_id: 222,
        deactivated: false,
        source_url: "/some/path/to/emoji",
        still_url: null,
    },
};

exports.fixtures = {
    alert_words: {
        type: "alert_words",
        alert_words: ["fire", "lunch"],
    },

    attachment__add: {
        type: "attachment",
        op: "add",
        attachment: {
            id: 99,
            name: "foo.png",
            size: 4096,
            path_id: "path_id",
            create_time: fake_now,
            messages: [
                {
                    id: 1000,
                    date_sent: fake_now,
                },
            ],
        },
        upload_space_used: 90000,
    },

    channel_folder__add: {
        type: "channel_folder",
        op: "add",
        channel_folder: {
            id: 1,
            name: "Frontend",
            description: "Channels for frontend discussions",
            rendered_description: "<p>Channels for frontend discussions</p>",
            date_created: 1681662420,
            creator_id: 10,
            is_archived: false,
        },
    },

    channel_typing_edit_message__start: {
        type: "typing_edit_message",
        op: "start",
        sender_id: typing_person1.user_id,
        message_id: 128,
        recipient: {
            type: "channel",
            channel_id: exports.stream_typing_in_id,
            topic: exports.topic_typing_in,
        },
    },

    channel_typing_edit_message__stop: {
        type: "typing_edit_message",
        op: "stop",
        sender_id: typing_person1.user_id,
        message_id: 128,
        recipient: {
            type: "channel",
            channel_id: exports.stream_typing_in_id,
            topic: exports.topic_typing_in,
        },
    },

    custom_profile_fields: {
        type: "custom_profile_fields",
        fields: [
            {
                id: 1,
                name: "teams",
                type: 1,
                hint: "",
                field_data: "",
                order: 1,
                display_in_profile_summary: false,
                required: false,
                editable_by_user: true,
            },
            {
                id: 2,
                name: "hobbies",
                type: 1,
                hint: "",
                field_data: "",
                order: 2,
                display_in_profile_summary: false,
                required: false,
                editable_by_user: false,
            },
        ],
    },

    default_streams: {
        type: "default_streams",
        default_streams: [streams.devel.stream_id, streams.test.stream_id],
    },

    delete_message: {
        type: "delete_message",
        message_ids: [1337],
        message_type: "stream",
        stream_id: 99,
        topic: "topic1",
    },

    has_zoom_token: {
        type: "has_zoom_token",
        value: true,
    },

    invites_changed: {
        type: "invites_changed",
    },

    message_edit_typing__start: {
        type: "typing_edit_message",
        op: "start",
        sender_id: typing_person1.user_id,
        message_id: 128,
        recipient: {
            type: "direct",
            user_ids: [typing_person2.user_id],
        },
    },

    message_edit_typing__stop: {
        type: "typing_edit_message",
        op: "stop",
        sender_id: typing_person1.user_id,
        message_id: 128,
        recipient: {
            type: "direct",
            user_ids: [typing_person2.user_id],
        },
    },

    muted_users: {
        type: "muted_users",
        muted_users: [
            {
                id: 5,
                timestamp: fake_then,
            },
            {
                id: 23,
                timestamp: fake_now,
            },
        ],
    },

    onboarding_steps: {
        type: "onboarding_steps",
        onboarding_steps: [
            {
                type: "one_time_notice",
                name: "intro_inbox_view_modal",
            },
            {
                type: "one_time_notice",
                name: "intro_recent_view_modal",
            },
        ],
    },

    presence: {
        type: "presence",
        email: "alice@example.com",
        user_id: 42,
        presence: {
            electron: {
                status: "active",
                timestamp: fake_now,
                client: "electron",
                pushable: false,
            },
        },
        server_timestamp: fake_now,
    },

    reaction__add: {
        type: "reaction",
        op: "add",
        message_id: 128,
        reaction_type: "unicode_emoji",
        emoji_name: "airplane",
        emoji_code: "2708",
        user_id: test_user.user_id,
        user: {
            email: test_user.email,
            full_name: test_user.full_name,
            user_id: test_user.user_id,
        },
    },

    reaction__remove: {
        type: "reaction",
        op: "remove",
        message_id: 256,
        reaction_type: "unicode_emoji",
        emoji_name: "8ball",
        emoji_code: "1f3b1",
        user_id: test_user.user_id,
        user: {
            email: test_user.email,
            full_name: test_user.full_name,
            user_id: test_user.user_id,
        },
    },

    realm__deactivated: {
        type: "realm",
        op: "deactivated",
        realm_id: 2,
    },

    realm__update__default_code_block_language: {
        type: "realm",
        op: "update",
        property: "default_code_block_language",
        value: "javascript",
    },

    realm__update__disallow_disposable_email_addresses: {
        type: "realm",
        op: "update",
        property: "disallow_disposable_email_addresses",
        value: false,
    },

    realm__update__emails_restricted_to_domains: {
        type: "realm",
        op: "update",
        property: "emails_restricted_to_domains",
        value: false,
    },

    realm__update__enable_spectator_access: {
        type: "realm",
        op: "update",
        property: "enable_spectator_access",
        value: true,
    },

    realm__update__invite_required: {
        type: "realm",
        op: "update",
        property: "invite_required",
        value: false,
    },

    realm__update__name: {
        type: "realm",
        op: "update",
        property: "name",
        value: "new_realm_name",
    },

    realm__update__new_stream_announcements_stream_id: {
        type: "realm",
        op: "update",
        property: "new_stream_announcements_stream_id",
        value: 42,
    },

    realm__update__org_type: {
        type: "realm",
        op: "update",
        property: "org_type",
        value: 50,
    },

    realm__update__signup_announcements_stream_id: {
        type: "realm",
        op: "update",
        property: "signup_announcements_stream_id",
        value: 41,
    },

    realm__update__want_advertise_in_communities_directory: {
        type: "realm",
        op: "update",
        property: "want_advertise_in_communities_directory",
        value: false,
    },

    realm__update__zulip_update_announcements_stream_id: {
        type: "realm",
        op: "update",
        property: "zulip_update_announcements_stream_id",
        value: 42,
    },

    realm__update_dict__default: {
        type: "realm",
        op: "update_dict",
        property: "default",
        data: {
            allow_message_editing: true,
            message_content_edit_limit_seconds: 5,
            create_multiuse_invite_group: 3,
            authentication_methods: {
                Google: {enabled: true, available: true},
            },
            can_add_custom_emoji_group: 3,
            can_add_subscribers_group: 3,
            can_create_bots_group: 3,
            can_create_public_channel_group: 3,
            can_invite_users_group: 3,
            can_move_messages_between_topics_group: 3,
            can_resolve_topics_group: 1,
            direct_message_permission_group: 3,
            plan_type: 3,
            upload_quota_mib: 50000,
            max_file_upload_size_mib: 1024,
            topics_policy: "disable_empty_topic",
        },
    },

    realm__update_dict__icon: {
        type: "realm",
        op: "update_dict",
        property: "icon",
        data: {
            icon_url: "icon.png",
            icon_source: "U",
        },
    },

    realm__update_dict__logo: {
        type: "realm",
        op: "update_dict",
        property: "logo",
        data: {
            logo_url: "logo.png",
            logo_source: "U",
        },
    },

    realm__update_dict__night_logo: {
        type: "realm",
        op: "update_dict",
        property: "night_logo",
        data: {
            night_logo_url: "night_logo.png",
            night_logo_source: "U",
        },
    },

    realm_bot__add: {
        type: "realm_bot",
        op: "add",
        bot: {
            email: "the-bot@example.com",
            user_id: 42,
            avatar_url: "/some/path/to/avatar",
            api_key: "SOME_KEY",
            full_name: "The Bot",
            bot_type: 1,
            default_all_public_streams: true,
            default_events_register_stream: "whatever",
            default_sending_stream: "whatever",
            is_active: true,
            owner_id: test_user.user_id,
            services: [],
        },
    },

    realm_bot__delete: {
        type: "realm_bot",
        op: "delete",
        bot: {
            user_id: 42,
        },
    },

    realm_bot__update: {
        type: "realm_bot",
        op: "update",
        bot: {
            user_id: 4321,
            full_name: "The Bot Has A New Name",
        },
    },

    realm_domains__add: {
        type: "realm_domains",
        op: "add",
        realm_domain: {
            domain: "ramen",
            allow_subdomains: false,
        },
    },

    realm_domains__change: {
        type: "realm_domains",
        op: "change",
        realm_domain: {
            domain: "ramen",
            allow_subdomains: true,
        },
    },

    realm_domains__remove: {
        type: "realm_domains",
        op: "remove",
        domain: "ramen",
    },

    realm_emoji__update: {
        type: "realm_emoji",
        op: "update",
        realm_emoji: exports.test_realm_emojis,
    },

    realm_export: {
        type: "realm_export",
        exports: [
            {
                id: 55,
                export_time: fake_now,
                acting_user_id: test_user.user_id,
                export_url: "/some/path/to/export",
                deleted_timestamp: null,
                failed_timestamp: null,
                pending: true,
                export_type: 1,
            },
        ],
    },

    realm_export_consent: {
        type: "realm_export_consent",
        user_id: test_user.user_id,
        consented: true,
    },

    realm_linkifiers: {
        type: "realm_linkifiers",
        realm_linkifiers: [
            {
                pattern: "#[123]",
                url_template: "ticket {id}",
                id: 55,
            },
        ],
    },

    realm_playgrounds: {
        type: "realm_playgrounds",
        realm_playgrounds: [
            {
                id: 1,
                name: "Lean playground",
                pygments_language: "Lean",
                url_template: "https://leanprover.github.io/live/latest/{#code}",
            },
        ],
    },

    realm_user__add: {
        type: "realm_user",
        op: "add",
        person: {
            ...test_user,
            avatar_url: "/some/path/to/avatar",
            avatar_version: 1,
            is_admin: false,
            is_active: true,
            is_owner: false,
            role: 400,
            is_bot: false,
            is_guest: false,
            profile_data: {},
            timezone: "America/New_York",
            date_joined: "2020-01-01",
            delivery_email: "test-delivery@example.com",
        },
    },

    realm_user__add_bot: {
        type: "realm_user",
        op: "add",
        person: {
            ...test_user,
            avatar_url: "/some/path/to/avatar",
            avatar_version: 1,
            is_admin: false,
            is_active: true,
            is_owner: false,
            role: 400,
            is_bot: true,
            is_guest: false,
            profile_data: {},
            timezone: "America/New_York",
            date_joined: "2020-01-01",
            delivery_email: "test-delivery@example.com",
        },
    },

    realm_user__remove: {
        type: "realm_user",
        op: "remove",
        person: {
            user_id: test_user.user_id,
            full_name: "Unknown user",
        },
    },

    realm_user__update: {
        type: "realm_user",
        op: "update",
        person: {
            user_id: test_user.user_id,
            full_name: "Bob NewName",
        },
    },

    realm_user_settings_defaults__emojiset: {
        type: "realm_user_settings_defaults",
        op: "update",
        property: "emojiset",
        value: "google",
    },

    realm_user_settings_defaults__notification_sound: {
        type: "realm_user_settings_defaults",
        op: "update",
        property: "notification_sound",
        value: "ding",
    },

    realm_user_settings_defaults__presence_enabled: {
        type: "realm_user_settings_defaults",
        op: "update",
        property: "presence_enabled",
        value: false,
    },

    restart: {
        type: "restart",
        zulip_version: "9.0-dev-753-gced3e85da9",
        zulip_merge_base: "9.0-dev-743-g54053c1d28",
        zulip_feature_level: 237,
        server_generation: 1707511515,
    },

    saved_snippets__add: {
        type: "saved_snippets",
        op: "add",
        saved_snippet: {
            id: 1,
            title: "Example",
            content: "Welcome to the organization.",
            date_created: 1681662420,
        },
    },

    saved_snippets__remove: {
        type: "saved_snippets",
        op: "remove",
        saved_snippet_id: 1,
    },

    saved_snippets__update: {
        type: "saved_snippets",
        op: "update",
        saved_snippet: {
            id: 1,
            title: "Example 2",
            content: "Welcome to the organization.",
            date_created: 1681662420,
        },
    },

    scheduled_messages__add: {
        type: "scheduled_messages",
        op: "add",
        scheduled_messages: [
            {
                scheduled_message_id: 17,
                type: "private",
                to: [6],
                content: "Hello there!",
                rendered_content: "<p>Hello there!</p>",
                scheduled_delivery_timestamp: 1681662420,
                failed: false,
            },
        ],
    },

    scheduled_messages__remove: {
        type: "scheduled_messages",
        op: "remove",
        scheduled_message_id: 17,
    },

    scheduled_messages__update: {
        type: "scheduled_messages",
        op: "update",
        scheduled_message: {
            scheduled_message_id: 17,
            type: "private",
            to: [6],
            content: "Hello there!",
            rendered_content: "<p>Hello there!</p>",
            scheduled_delivery_timestamp: 1681662420,
            failed: false,
        },
    },

    stream__create: {
        type: "stream",
        op: "create",
        streams: [
            {
                ...streams.devel,
                stream_weekly_traffic: null,
            },
            {
                ...streams.test,
                stream_weekly_traffic: null,
            },
        ],
    },

    stream__delete: {
        type: "stream",
        op: "delete",
        streams: [
            {
                stream_id: streams.devel.stream_id,
            },
            {
                stream_id: streams.test.stream_id,
            },
        ],
        stream_ids: [streams.devel.stream_id, streams.test.stream_id],
    },

    stream__update: {
        type: "stream",
        op: "update",
        name: "devel",
        stream_id: 99,
        property: "color",
        value: "blue",
    },

    stream_typing__start: {
        type: "typing",
        op: "start",
        message_type: "stream",
        sender: typing_person1,
        stream_id: exports.stream_typing_in_id,
        topic: exports.topic_typing_in,
    },

    stream_typing__stop: {
        type: "typing",
        op: "stop",
        message_type: "stream",
        sender: typing_person1,
        stream_id: exports.stream_typing_in_id,
        topic: exports.topic_typing_in,
    },

    submessage: {
        type: "submessage",
        submessage_id: 99,
        sender_id: 42,
        msg_type: "stream",
        message_id: 56,
        content: "test",
    },

    subscription__add: {
        type: "subscription",
        op: "add",
        subscriptions: [
            {
                ...streams.devel,
                audible_notifications: true,
                color: "blue",
                desktop_notifications: false,
                email_notifications: false,
                in_home_view: false,
                is_muted: true,
                pin_to_top: false,
                push_notifications: false,
                stream_weekly_traffic: 40,
                wildcard_mentions_notify: false,
                subscribers: [5, 8, 13, 21],
            },
        ],
    },

    subscription__peer_add: {
        type: "subscription",
        op: "peer_add",
        user_ids: [test_user.user_id],
        stream_ids: [streams.devel.stream_id],
    },

    subscription__peer_remove: {
        type: "subscription",
        op: "peer_remove",
        user_ids: [test_user.user_id],
        stream_ids: [streams.devel.stream_id],
    },

    subscription__remove: {
        type: "subscription",
        op: "remove",
        subscriptions: [
            {
                name: "devel",
                stream_id: 42,
            },
        ],
    },

    subscription__update: {
        type: "subscription",
        op: "update",
        stream_id: streams.devel.stream_id,
        property: "pin_to_top",
        value: true,
    },

    typing__start: {
        type: "typing",
        op: "start",
        message_type: "direct",
        sender: typing_person1,
        recipients: [typing_person2],
    },

    typing__stop: {
        type: "typing",
        op: "stop",
        message_type: "direct",
        sender: typing_person1,
        recipients: [typing_person2],
    },

    update_message_flags__read: {
        type: "update_message_flags",
        op: "add",
        operation: "add",
        flag: "read",
        messages: [999],
        all: false,
    },

    update_message_flags__read_remove: {
        type: "update_message_flags",
        op: "remove",
        operation: "remove",
        flag: "read",
        messages: [888],
        message_details: {888: message_detail},
        all: false,
    },

    update_message_flags__starred_add: {
        type: "update_message_flags",
        op: "add",
        operation: "add",
        flag: "starred",
        messages: [exports.test_message.id],
        all: false,
    },

    update_message_flags__starred_remove: {
        type: "update_message_flags",
        op: "remove",
        operation: "remove",
        flag: "starred",
        messages: [exports.test_message.id],
        all: false,
    },

    user_group__add: {
        type: "user_group",
        op: "add",
        group: {
            id: 555,
            name: "Mobile",
            creator_id: null,
            date_created: fake_now,
            description: "mobile folks",
            members: [1],
            is_system_group: false,
            direct_subgroup_ids: [2],
            can_add_members_group: 16,
            can_join_group: 16,
            can_leave_group: 15,
            can_manage_group: 16,
            can_mention_group: 11,
            can_remove_members_group: 16,
            deactivated: false,
        },
    },

    user_group__add_members: {
        type: "user_group",
        op: "add_members",
        group_id: 1,
        user_ids: [2],
    },

    user_group__add_subgroups: {
        type: "user_group",
        op: "add_subgroups",
        group_id: 1,
        direct_subgroup_ids: [3],
    },

    user_group__remove_members: {
        type: "user_group",
        op: "remove_members",
        group_id: 1,
        user_ids: [1, 2],
    },

    user_group__remove_subgroups: {
        type: "user_group",
        op: "remove_subgroups",
        group_id: 1,
        direct_subgroup_ids: [3],
    },

    user_group__update: {
        type: "user_group",
        op: "update",
        group_id: 1,
        data: {
            name: "Frontend",
            description: "All Frontend people",
            can_manage_group: 2,
        },
    },

    user_settings__allow_private_data_export: {
        type: "user_settings",
        op: "update",
        property: "allow_private_data_export",
        value: true,
    },

    user_settings__color_scheme_automatic: {
        type: "user_settings",
        op: "update",
        property: "color_scheme",
        value: 1,
    },

    user_settings__color_scheme_dark: {
        type: "user_settings",
        op: "update",
        property: "color_scheme",
        value: 2,
    },

    user_settings__color_scheme_light: {
        type: "user_settings",
        op: "update",
        property: "color_scheme",
        value: 3,
    },

    user_settings__default_language: {
        type: "user_settings",
        op: "update",
        property: "default_language",
        value: "fr",
        language_name: "French",
    },

    user_settings__demote_inactive_streams: {
        type: "user_settings",
        op: "update",
        property: "demote_inactive_streams",
        value: 2,
    },

    user_settings__display_emoji_reaction_users: {
        type: "user_settings",
        op: "update",
        property: "display_emoji_reaction_users",
        value: true,
    },

    user_settings__email_address_visibility: {
        type: "user_settings",
        op: "update",
        property: "email_address_visibility",
        value: 5,
    },

    user_settings__emojiset: {
        type: "user_settings",
        op: "update",
        property: "emojiset",
        value: "google",
    },

    user_settings__enable_stream_audible_notifications: {
        type: "user_settings",
        op: "update",
        property: "enable_stream_audible_notifications",
        value: true,
    },

    user_settings__enter_sends: {
        type: "user_settings",
        op: "update",
        property: "enter_sends",
        value: true,
    },

    user_settings__fluid_layout_width: {
        type: "user_settings",
        op: "update",
        property: "fluid_layout_width",
        value: true,
    },

    user_settings__high_contrast_mode: {
        type: "user_settings",
        op: "update",
        property: "high_contrast_mode",
        value: true,
    },

    user_settings__notification_sound: {
        type: "user_settings",
        op: "update",
        property: "notification_sound",
        value: "ding",
    },

    user_settings__presence_disabled: {
        type: "user_settings",
        op: "update",
        property: "presence_enabled",
        value: false,
    },

    user_settings__presence_enabled: {
        type: "user_settings",
        op: "update",
        property: "presence_enabled",
        value: true,
    },

    user_settings__receives_typing_notifications: {
        type: "user_settings",
        op: "update",
        property: "receives_typing_notifications",
        value: true,
    },

    user_settings__receives_typing_notifications_disabled: {
        type: "user_settings",
        op: "update",
        property: "receives_typing_notifications",
        value: false,
    },

    user_settings__starred_message_counts: {
        type: "user_settings",
        op: "update",
        property: "starred_message_counts",
        value: true,
    },

    user_settings__translate_emoticons: {
        type: "user_settings",
        op: "update",
        property: "translate_emoticons",
        value: true,
    },

    user_settings__twenty_four_hour_time: {
        type: "user_settings",
        op: "update",
        property: "twenty_four_hour_time",
        value: true,
    },

    user_settings__user_list_style: {
        type: "user_settings",
        op: "update",
        property: "user_list_style",
        value: 2,
    },

    user_settings__web_animate_image_previews_always: {
        type: "user_settings",
        op: "update",
        property: "web_animate_image_previews",
        value: "always",
    },

    user_settings__web_animate_image_previews_never: {
        type: "user_settings",
        op: "update",
        property: "web_animate_image_previews",
        value: "never",
    },

    user_settings__web_animate_image_previews_on_hover: {
        type: "user_settings",
        op: "update",
        property: "web_animate_image_previews",
        value: "on_hover",
    },

    user_settings__web_channel_default_view: {
        type: "user_settings",
        op: "update",
        property: "web_channel_default_view",
        value: 1,
    },

    user_settings__web_escape_navigates_to_home_view: {
        type: "user_settings",
        op: "update",
        property: "web_escape_navigates_to_home_view",
        value: true,
    },

    user_settings__web_font_size_px: {
        type: "user_settings",
        op: "update",
        property: "web_font_size_px",
        value: 16,
    },

    user_settings__web_home_view_all_messages: {
        type: "user_settings",
        op: "update",
        property: "web_home_view",
        value: "all_messages",
    },

    user_settings__web_home_view_inbox: {
        type: "user_settings",
        op: "update",
        property: "web_home_view",
        value: "inbox",
    },

    user_settings__web_home_view_recent_topics: {
        type: "user_settings",
        op: "update",
        property: "web_home_view",
        value: "recent_topics",
    },

    user_settings__web_line_height_percent: {
        type: "user_settings",
        op: "update",
        property: "web_line_height_percent",
        value: 130,
    },

    user_settings__web_mark_read_on_scroll_policy: {
        type: "user_settings",
        op: "update",
        property: "web_mark_read_on_scroll_policy",
        value: 1,
    },

    user_settings__web_navigate_to_sent_message: {
        type: "user_settings",
        op: "update",
        property: "web_navigate_to_sent_message",
        value: false,
    },

    user_settings__web_stream_unreads_count_display_policy: {
        type: "user_settings",
        op: "update",
        property: "web_stream_unreads_count_display_policy",
        value: 2,
    },

    user_settings_web_suggest_update_timezone: {
        type: "user_settings",
        op: "update",
        property: "web_suggest_update_timezone",
        value: true,
        id: 1,
    },

    user_status__set_status_emoji: {
        id: 1,
        type: "user_status",
        user_id: test_user.user_id,
        emoji_name: "smiley",
        emoji_code: "1f603",
        reaction_type: "unicode_emoji",
        status_text: "",
    },

    user_status__set_status_text: {
        type: "user_status",
        user_id: test_user.user_id,
        status_text: "out to lunch",
    },

    user_topic: {
        type: "user_topic",
        stream_id: 101,
        topic_name: "js",
        last_updated: fake_now,
        visibility_policy: 1,
    },

    user_topic_with_followed_policy_change: {
        type: "user_topic",
        stream_id: 101,
        topic_name: "js",
        last_updated: fake_now,
        visibility_policy: 3,
    },

    web_reload_client: {
        type: "web_reload_client",
        immediate: true,
    },
};
