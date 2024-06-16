"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {user_settings} = require("./lib/zpage_params");

const settings_config = zrequire("settings_config");

run_test("all_notifications", () => {
    user_settings.enable_stream_desktop_notifications = false;
    user_settings.enable_stream_audible_notifications = true;
    user_settings.enable_stream_push_notifications = true;
    user_settings.enable_stream_email_notifications = false;
    user_settings.enable_desktop_notifications = false;
    user_settings.enable_sounds = true;
    user_settings.enable_offline_push_notifications = false;
    user_settings.enable_offline_email_notifications = true;
    user_settings.enable_followed_topic_desktop_notifications = false;
    user_settings.enable_followed_topic_audible_notifications = true;
    user_settings.enable_followed_topic_push_notifications = false;
    user_settings.enable_followed_topic_email_notifications = true;
    user_settings.enable_followed_topic_wildcard_mentions_notify = false;

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

    user_settings.wildcard_mentions_notify = false;
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
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_stream_audible_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: true,
                    is_mobile_checkbox: true,
                    setting_name: "enable_stream_push_notifications",
                },
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_stream_email_notifications",
                },
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "wildcard_mentions_notify",
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
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_sounds",
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    is_mobile_checkbox: true,
                    setting_name: "enable_offline_push_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_offline_email_notifications",
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    is_mobile_checkbox: false,
                    setting_name: "",
                },
            ],
        },
        {
            label: "translated: Followed topics",
            notification_settings: [
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_desktop_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_audible_notifications",
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    is_mobile_checkbox: true,
                    setting_name: "enable_followed_topic_push_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_email_notifications",
                },
                {
                    is_checked: false,
                    is_disabled: false,
                    is_mobile_checkbox: false,
                    setting_name: "enable_followed_topic_wildcard_mentions_notify",
                },
            ],
        },
    ]);
});
