/*
    This file contains translations between the integer values used in
    the Zulip API to describe values in dropdowns, radio buttons, and
    similar widgets and the user-facing strings that should be used to
    describe them, as well as data details like sort orders that may
    be useful for some widgets.

    We plan to eventually transition much of this file to have a more
    standard format and then to be populated using data sent from the
    Zulip server in `page_params`, so that the data is available for
    other parts of the ecosystem to use (including the mobile apps and
    API documentation) without a ton of copying.
*/

exports.demote_inactive_streams_values = {
    automatic: {
        code: 1,
        description: i18n.t("Automatic"),
    },
    always: {
        code: 2,
        description: i18n.t("Always"),
    },
    never: {
        code: 3,
        description: i18n.t("Never"),
    },
};

exports.twenty_four_hour_time_values = {
    twenty_four_hour_clock: {
        value: true,
        description: i18n.t("24-hour clock (17:00)"),
    },
    twelve_hour_clock: {
        value: false,
        description: i18n.t("12-hour clock (5:00 PM)"),
    },
};

exports.get_all_display_settings = () => ({
    settings: {
        user_display_settings: [
            "dense_mode",
            "night_mode",
            "high_contrast_mode",
            "left_side_userlist",
            "starred_message_counts",
            "fluid_layout_width",
        ],
    },
    render_only: {
        high_contrast_mode: page_params.development_environment,
        dense_mode: page_params.development_environment,
    },
});

exports.email_address_visibility_values = {
    everyone: {
        code: 1,
        description: i18n.t("Admins, members, and guests"),
    },
    //// Backend support for this configuration is not available yet.
    // admins_and_members: {
    //     code: 2,
    //     description: i18n.t("Members and admins"),
    // },
    admins_only: {
        code: 3,
        description: i18n.t("Admins only"),
    },
    nobody: {
        code: 4,
        description: i18n.t("Nobody"),
    },
};

exports.create_stream_policy_values = {
    by_admins_only: {
        order: 1,
        code: 2,
        description: i18n.t("Admins"),
    },
    by_full_members: {
        order: 2,
        code: 3,
        description: i18n.t("Admins and full members"),
    },
    by_members: {
        order: 3,
        code: 1,
        description: i18n.t("Admins and members"),
    },
};

exports.buddy_list_mode_values = {
    all_users: {
        value: 1,
        description: i18n.t("All users"),
    },
    stream_or_pm_members: {
        value: 2,
        description: i18n.t("Stream or PM recipients"),
    },
};

exports.invite_to_stream_policy_values = exports.create_stream_policy_values;

exports.user_group_edit_policy_values = {
    by_admins_only: {
        order: 1,
        code: 2,
        description: i18n.t("Admins"),
    },
    by_members: {
        order: 2,
        code: 1,
        description: i18n.t("Admins and members"),
    },
};

exports.private_message_policy_values = {
    by_anyone: {
        order: 1,
        code: 1,
        description: i18n.t("Admins, members, and guests"),
    },
    disabled: {
        order: 2,
        code: 2,
        description: i18n.t("Private messages disabled"),
    },
};

const time_limit_dropdown_values = new Map([
    ["any_time", {
        text: i18n.t("Any time"),
        seconds: 0,
    }],
    ["never", {
        text: i18n.t("Never"),
    }],
    ["upto_two_min", {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("2 minutes")}),
        seconds: 2 * 60,
    }],
    ["upto_ten_min", {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("10 minutes")}),
        seconds: 10 * 60,
    }],
    ["upto_one_hour", {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 hour")}),
        seconds: 60 * 60,
    }],
    ["upto_one_day", {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 day")}),
        seconds: 24 * 60 * 60,
    }],
    ["upto_one_week", {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 week")}),
        seconds: 7 * 24 * 60 * 60,
    }],
    ["custom_limit", {
        text: i18n.t("Up to N minutes after posting"),
    }],
]);
exports.msg_edit_limit_dropdown_values = time_limit_dropdown_values;
exports.msg_delete_limit_dropdown_values = time_limit_dropdown_values;

exports.retain_message_forever = -1;

// NOTIFICATIONS

exports.general_notifications_table_labels = {
    realm: [
        /* An array of notification settings of any category like
        * `stream_notification_settings` which makes a single row of
        * "Notification triggers" table should follow this order
        */
        "visual", "audio", "mobile", "email", "all_mentions",
    ],
    stream: {
        is_muted: i18n.t("Mute stream"),
        desktop_notifications: i18n.t("Visual desktop notifications"),
        audible_notifications: i18n.t("Audible desktop notifications"),
        push_notifications: i18n.t("Mobile notifications"),
        email_notifications: i18n.t("Email notifications"),
        pin_to_top: i18n.t("Pin stream to top of left sidebar"),
        wildcard_mentions_notify: i18n.t("Notifications for @all/@everyone mentions"),
    },
};

exports.stream_specific_notification_settings = [
    "desktop_notifications",
    "audible_notifications",
    "push_notifications",
    "email_notifications",
    "wildcard_mentions_notify",
];

exports.stream_notification_settings = [
    "enable_stream_desktop_notifications",
    "enable_stream_audible_notifications",
    "enable_stream_push_notifications",
    "enable_stream_email_notifications",
    "wildcard_mentions_notify",
];

const pm_mention_notification_settings = [
    "enable_desktop_notifications",
    "enable_sounds",
    "enable_offline_push_notifications",
    "enable_offline_email_notifications",
];

const desktop_notification_settings = [
    "pm_content_in_desktop_notifications",
];

const mobile_notification_settings = [
    "enable_online_push_notifications",
];

const email_notification_settings = [
    "enable_digest_emails",
    "enable_login_emails",
    "message_content_in_email_notifications",
    "realm_name_in_notifications",
];

const presence_notification_settings = [
    "presence_enabled",
];

const other_notification_settings = desktop_notification_settings.concat(
    ["desktop_icon_count_display"],
    mobile_notification_settings,
    email_notification_settings,
    presence_notification_settings,
    ["notification_sound"]
);

exports.all_notification_settings = other_notification_settings.concat(
    pm_mention_notification_settings,
    exports.stream_notification_settings
);

exports.all_notifications = () => ({
    general_settings: [
        {
            label: i18n.t("Streams"),
            notification_settings: settings_notifications.get_notifications_table_row_data(
                exports.stream_notification_settings),
        },
        {
            label: i18n.t("PMs, mentions, and alerts"),
            notification_settings: settings_notifications.get_notifications_table_row_data(
                pm_mention_notification_settings),
        },
    ],
    settings: {
        desktop_notification_settings: desktop_notification_settings,
        mobile_notification_settings: mobile_notification_settings,
        email_notification_settings: email_notification_settings,
        presence_notification_settings: presence_notification_settings,
    },
    show_push_notifications_tooltip: {
        push_notifications: !page_params.realm_push_notifications_enabled,
        enable_online_push_notifications: !page_params.realm_push_notifications_enabled,
    },
});
