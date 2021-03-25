"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {page_params} = require("../zjsunit/zpage_params");

const settings_config = zrequire("settings_config");

run_test("all_notifications", () => {
    page_params.enable_stream_desktop_notifications = false;
    page_params.enable_stream_audible_notifications = true;
    page_params.enable_stream_push_notifications = true;
    page_params.enable_stream_email_notifications = false;
    page_params.enable_desktop_notifications = false;
    page_params.enable_sounds = true;
    page_params.enable_offline_push_notifications = false;
    page_params.enable_offline_email_notifications = true;

    const notifications = settings_config.all_notifications();

    assert.deepEqual(notifications.general_settings, [
        {
            label: "translated: Streams",
            notification_settings: [
                {
                    is_checked: false,
                    is_disabled: false,
                    setting_name: "enable_stream_desktop_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    setting_name: "enable_stream_audible_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: true,
                    setting_name: "enable_stream_push_notifications",
                },
                {
                    is_checked: false,
                    is_disabled: false,
                    setting_name: "enable_stream_email_notifications",
                },
                {
                    is_checked: undefined,
                    is_disabled: false,
                    setting_name: "wildcard_mentions_notify",
                },
            ],
        },
        {
            label: "translated: PMs, mentions, and alerts",
            notification_settings: [
                {
                    is_checked: false,
                    is_disabled: false,
                    setting_name: "enable_desktop_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    setting_name: "enable_sounds",
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    setting_name: "enable_offline_push_notifications",
                },
                {
                    is_checked: true,
                    is_disabled: false,
                    setting_name: "enable_offline_email_notifications",
                },
                {
                    is_checked: false,
                    is_disabled: true,
                    setting_name: "",
                },
            ],
        },
    ]);
});
