"use strict";

zrequire("templates");

// We download our translations in `page_params` (which
// are for the user's chosen language), so we simulate
// that here for the tests.
set_global("page_params", {
    translation_data: {
        "Quote and reply or forward": "French translation",
        "Notification triggers": "Some French text",
    },
});

// All of our other tests stub out i18n activity;
// here we do a quick sanity check on the engine itself.
// We use `i18n.js` to initialize `i18next` and
// to set `i18n` to `i18next` on the global namespace
// for `templates.js`.
zrequire("i18n");

run_test("t_tag", () => {
    const args = {
        message: {
            is_stream: true,
            id: "99",
            stream: "devel",
            subject: "testing",
            sender_full_name: "King Lear",
        },
        should_display_quote_and_reply: true,
        can_edit_message: true,
        can_mute_topic: true,
        narrowed: true,
    };

    const html = require("../../static/templates/actions_popover_content.hbs")(args);
    assert(html.indexOf("French translation") > 0);
});

run_test("tr_tag", () => {
    const args = {
        page_params: {
            full_name: "John Doe",
            password_auth_enabled: false,
            avatar_url: "http://example.com",
            left_side_userlist: false,
            twenty_four_hour_time: false,
            enable_stream_desktop_notifications: false,
            enable_stream_push_notifications: false,
            enable_stream_audible_notifications: false,
            enable_desktop_notifications: false,
            enable_sounds: false,
            enable_offline_email_notifications: false,
            enable_offline_push_notifications: false,
            enable_online_push_notifications: false,
            enable_digest_emails: false,
        },
    };

    const html = require("../../static/templates/settings_tab.hbs")(args);
    assert(html.indexOf("Some French text") > 0);
});
