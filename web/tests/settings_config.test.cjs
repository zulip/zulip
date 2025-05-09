"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const settings_config = zrequire("settings_config");
const {set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {realm_push_notifications_enabled: false};
set_realm(realm);
const user_settings = {};
initialize_user_settings({user_settings});

run_test("all_notifications", ({override}) => {
    override(user_settings, "enable_stream_desktop_notifications", false);
    override(user_settings, "enable_stream_audible_notifications", true);
    override(user_settings, "enable_stream_push_notifications", true);
    override(user_settings, "enable_stream_email_notifications", false);
    override(user_settings, "enable_desktop_notifications", false);
    override(user_settings, "enable_sounds", true);
    override(user_settings, "enable_offline_push_notifications", false);
    override(user_settings, "enable_offline_email_notifications", true);
    override(user_settings, "enable_followed_topic_desktop_notifications", false);
    override(user_settings, "enable_followed_topic_audible_notifications", true);
    override(user_settings, "enable_followed_topic_push_notifications", false);
    override(user_settings, "enable_followed_topic_email_notifications", true);
    override(user_settings, "enable_followed_topic_wildcard_mentions_notify", false);

    // Check that it throws error if incorrect settings name
    // is passed. In this case, we articulate that with
    // wildcard_mentions_notify being undefined, which will be
    // the case, if a wrong setting_name is passed.
    let error_message;
    let error_name;
    try {
        settings_config.all_notifications(user_settings);
    } catch (error) {
        error_name = error.name;
        error_message = error.message;
    }
    assert.equal(error_name, "TypeError");
    assert.equal(error_message, "Incorrect setting_name passed: wildcard_mentions_notify");

    override(user_settings, "wildcard_mentions_notify", false);
    const notifications = settings_config.all_notifications(user_settings);

    assert.deepEqual(notifications.general_settings, [
        {
            label: "translated: Channels",
            notification_settings: [
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_stream_desktop_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_stream_audible_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: true,
                    is_disabled: true,
                    is_mobile_checkbox: true,
                    setting_name: "enable_stream_push_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_stream_email_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "wildcard_mentions_notify",
                    push_notifications_disabled: true,
                },
            ],
        },
        {
            label: "translated: DMs, mentions, and alerts",
            notification_settings: [
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_desktop_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_sounds",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    is_mobile_checkbox: true,
                    setting_name: "enable_offline_push_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_offline_email_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    is_mobile_checkbox: false,
                    setting_name: "",
                    push_notifications_disabled: false,
                },
            ],
        },
        {
            label: "translated: Followed topics",
            help_link: "/help/follow-a-topic",
            notification_settings: [
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_desktop_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_audible_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    is_mobile_checkbox: true,
                    setting_name: "enable_followed_topic_push_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_email_notifications",
                    push_notifications_disabled: true,
                },
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_wildcard_mentions_notify",
                    push_notifications_disabled: true,
                },
            ],
        },
    ]);
});

run_test("customize_stream_notifications_table_row_data", () => {
    const customize_stream_notifications_table_row_data =
        settings_config.get_custom_stream_specific_notifications_table_row_data();

    assert.deepEqual(customize_stream_notifications_table_row_data, [
        {
            is_checked: false,
            is_disabled: true,
            is_mobile_checkbox: false,
            setting_name: "desktop_notifications",
            push_notifications_disabled: true,
        },
        {
            is_checked: false,
            is_disabled: true,
            is_mobile_checkbox: false,
            setting_name: "audible_notifications",
            push_notifications_disabled: true,
        },
        {
            is_checked: false,
            is_disabled: true,
            is_mobile_checkbox: true,
            setting_name: "push_notifications",
            push_notifications_disabled: true,
        },
        {
            is_checked: false,
            is_disabled: true,
            is_mobile_checkbox: false,
            setting_name: "email_notifications",
            push_notifications_disabled: true,
        },
        {
            is_checked: false,
            is_disabled: true,
            is_mobile_checkbox: false,
            setting_name: "wildcard_mentions_notify",
            push_notifications_disabled: true,
        },
    ]);
});
