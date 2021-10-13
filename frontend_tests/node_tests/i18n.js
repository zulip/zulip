"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {unmock_module, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const {page_params} = require("../zjsunit/zpage_params");

// We download our translations in `page_params` (which
// are for the user's chosen language), so we simulate
// that here for the tests.
page_params.request_language = "en";
page_params.translation_data = {
    "Quote and reply or forward": "Citer et répondre ou transférer",
    "Notification triggers": "Déclencheurs de notification",
    "You subscribed to stream {stream}": "Vous n'êtes pas abonnés au canal {stream}",
    "<p>The stream <b>{stream_name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Streams page</z-link>.</p>":
        "<p>Le canal <b>{stream_name}</b> n'existe pas.</p><p>Gérez vos abonnements <z-link>sur votre page canaux</z-link>.</p>",
};

// Re-register Zulip extensions so extensions registered previously with
// mocked i18n.ts do not interefere with following tests.
require("../../static/js/templates");

// All of our other tests stub out i18n activity;
// here we do a quick sanity check on the engine itself.
// `i18n.js` initializes FormatJS and is imported by
// `templates.js`.
unmock_module("../../static/js/i18n");
const {$t, $t_html, get_language_name, get_language_list_columns, initialize} = zrequire("i18n");

run_test("$t", () => {
    // Normally the id would be provided by babel-plugin-formatjs, but
    // this test file is not processed by Babel.
    assert.equal(
        $t({id: "Quote and reply or forward", defaultMessage: "Quote and reply or forward"}),
        "Citer et répondre ou transférer",
    );
    assert.equal(
        $t(
            {
                id: "You subscribed to stream {stream}",
                defaultMessage: "You subscribed to stream {stream}",
            },
            {stream: "l'abonnement"},
        ),
        "Vous n'êtes pas abonnés au canal l'abonnement",
    );
});

run_test("$tr", () => {
    assert.equal(
        $t_html(
            {
                id: "<p>The stream <b>{stream_name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Streams page</z-link>.</p>",
                defaultMessage:
                    "<p>The stream <b>{stream_name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Streams page</z-link>.</p>",
            },
            {
                stream_name: "l'abonnement",
                "z-link": (content_html) => `<a href='#streams/all'>${content_html}</a>`,
            },
        ),
        "<p>Le canal <b>l&#39;abonnement</b> n'existe pas.</p><p>Gérez vos abonnements <a href='#streams/all'>sur votre page canaux</a>.</p>",
    );
});

run_test("t_tag", ({mock_template}) => {
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
        topic: "testing",
        not_spectator: true,
    };

    mock_template("actions_popover_content.hbs", true, (data, html) => {
        assert.equal(data, args);
        assert.ok(html.indexOf("Citer et répondre ou transférer") > 0);
    });

    require("../../static/templates/actions_popover_content.hbs")(args);
});

run_test("tr_tag", ({mock_template}) => {
    const args = {
        page_params: {
            full_name: "John Doe",
            password_auth_enabled: false,
            avatar_url: "http://example.com",
        },
        user_settings: {
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

    mock_template("settings_tab.hbs", true, (data, html) => {
        assert.equal(data, args);
        assert.ok(html.indexOf("Déclencheurs de notification") > 0);
    });
    require("../../static/templates/settings_tab.hbs")(args);
});

run_test("language_list", () => {
    const language_list = [
        {
            code: "en",
            locale: "en",
            name: "English",
        },
        {
            code: "en-gb",
            locale: "en_GB",
            name: "British English",
            percent_translated: 99,
        },
        {
            code: "id",
            locale: "id",
            name: "Bahasa Indonesia",
            percent_translated: 32,
        },
    ];
    initialize({language_list});
    assert.equal(get_language_name("en"), "English");

    const successful_formatted_list = [
        {
            first: {
                name: "English",
                code: "en",
                name_with_percent: "English",
                selected: true,
            },
            second: {
                name: "Bahasa Indonesia",
                code: "id",
                name_with_percent: "Bahasa Indonesia (32%)",
                selected: false,
            },
        },
        {
            first: {
                name: "British English",
                code: "en-gb",
                name_with_percent: "British English (99%)",
                selected: false,
            },
        },
    ];

    const formatted_list = get_language_list_columns("en");

    function check_value_match(element, position) {
        assert.equal(
            formatted_list[element][position].name,
            successful_formatted_list[element][position].name,
        );
        assert.equal(
            formatted_list[element][position].code,
            successful_formatted_list[element][position].code,
        );
        assert.equal(
            formatted_list[element][position].name_with_percent,
            successful_formatted_list[element][position].name_with_percent,
        );
        assert.equal(
            formatted_list[element][position].selected,
            successful_formatted_list[element][position].selected,
        );
    }

    for (const element of _.range(0, formatted_list.length)) {
        check_value_match(element, "first");
        if (formatted_list[element].second) {
            check_value_match(element, "second");
        }
    }
});
