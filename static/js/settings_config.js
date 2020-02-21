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

const time_limit_dropdown_values = {
    any_time: {
        text: i18n.t("Any time"),
        seconds: 0,
    },
    never: {
        text: i18n.t("Never"),
    },
    upto_two_min: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("2 minutes")}),
        seconds: 2 * 60,
    },
    upto_ten_min: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("10 minutes")}),
        seconds: 10 * 60,
    },
    upto_one_hour: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 hour")}),
        seconds: 60 * 60,
    },
    upto_one_day: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 day")}),
        seconds: 24 * 60 * 60,
    },
    upto_one_week: {
        text: i18n.t("Up to __time_limit__ after posting", {time_limit: i18n.t("1 week")}),
        seconds: 7 * 24 * 60 * 60,
    },
    custom_limit: {
        text: i18n.t("Up to N minutes after posting"),
    },
};
exports.msg_edit_limit_dropdown_values = time_limit_dropdown_values;
exports.msg_delete_limit_dropdown_values = time_limit_dropdown_values;
