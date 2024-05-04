"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {unmock_module, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params} = require("./lib/zpage_params");

// We download our translations in `page_params` (which
// are for the user's chosen language), so we simulate
// that here for the tests.
page_params.request_language = "en";
page_params.translation_data = {
    "Quote and reply": "Citer et répondre",
    "Notification triggers": "Déclencheurs de notification",
    "You subscribed to channel {name}": "Vous n'êtes pas abonnés au canal {name}",
    "<p>The channel <b>{name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Channels page</z-link>.</p>":
        "<p>Le canal <b>{name}</b> n'existe pas.</p><p>Gérez vos abonnements <z-link>sur votre page canaux</z-link>.</p>",
};

// Re-register Zulip extensions so extensions registered previously with
// mocked i18n.ts do not interfere with following tests.
require("../src/templates");

// All of our other tests stub out i18n activity;
// here we do a quick sanity check on the engine itself.
// `i18n.ts` initializes FormatJS and is imported by
// `templates.js`.
unmock_module("../src/i18n");
const {$t, $t_html, get_language_name, get_language_list_columns, initialize} = zrequire("i18n");

run_test("$t", () => {
    // Normally the id would be provided by babel-plugin-formatjs, but
    // this test file is not processed by Babel.
    assert.equal(
        $t({id: "Quote and reply", defaultMessage: "Quote and reply"}),
        "Citer et répondre",
    );
    assert.equal(
        $t(
            {
                id: "You subscribed to channel {name}",
                defaultMessage: "You subscribed to channel {name}",
            },
            {name: "l'abonnement"},
        ),
        "Vous n'êtes pas abonnés au canal l'abonnement",
    );
});

run_test("$tr", () => {
    assert.equal(
        $t_html(
            {
                id: "<p>The channel <b>{name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Channels page</z-link>.</p>",
                defaultMessage:
                    "<p>The channel <b>{name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Channels page</z-link>.</p>",
            },
            {
                name: "l'abonnement",
                "z-link": (content_html) => `<a href='#channels/all'>${content_html.join("")}</a>`,
            },
        ),
        "<p>Le canal <b>l&#39;abonnement</b> n'existe pas.</p><p>Gérez vos abonnements <a href='#channels/all'>sur votre page canaux</a>.</p>",
    );
});

run_test("t_tag", ({mock_template}) => {
    const args = {
        message_id: "99",
        should_display_quote_and_reply: true,
        editability_menu_item: true,
        should_display_hide_option: true,
        conversation_time_url:
            "http://zulip.zulipdev.com/#narrow/stream/101-devel/topic/testing/near/99",
    };

    mock_template("popovers/actions_popover.hbs", true, (data, html) => {
        assert.equal(data, args);
        assert.ok(html.includes("Citer et répondre"));
    });

    require("../templates/popovers/actions_popover.hbs")(args);
});

run_test("tr_tag", ({mock_template}) => {
    const args = {
        botserverrc: "botserverrc",
        date_joined_text: "Mar 21, 2022",
        information_density_settings: {
            settings: {},
        },
        display_settings: {
            settings: {},
        },
        notification_settings: {},
        current_user: {
            full_name: "John Doe",
            delivery_email: "john@zulip.com",
        },
        page_params: {},
        realm: {},
        settings_object: {},
        settings_label: {
            desktop_icon_count_display:
                "Unread count badge (appears in desktop sidebar and browser tab)",
            realm_name_in_email_notifications_policy:
                "Include organization name in subject of message notification emails",
            twenty_four_hour_time: "Time format",
            automatically_follow_topics_policy: "Automatically follow topics",
            automatically_unmute_topics_in_muted_streams_policy:
                "Automatically unmute topics in muted channels",
            automatically_follow_topics_where_mentioned:
                "Automatically follow topics where I'm mentioned",
        },
        show_push_notifications_tooltip: false,
        user_role_text: "Member",
    };

    mock_template("settings_tab.hbs", true, (data, html) => {
        assert.equal(data, args);
        assert.ok(html.includes("Déclencheurs de notification"));
    });
    require("../templates/settings_tab.hbs")(args);
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
            name: "English",
            code: "en",
            name_with_percent: "English",
            selected: true,
        },
        {
            name: "British English",
            code: "en-gb",
            name_with_percent: "British English (99%)",
            selected: false,
        },
        {
            name: "Bahasa Indonesia",
            code: "id",
            name_with_percent: "Bahasa Indonesia (32%)",
            selected: false,
        },
    ];

    const formatted_list = get_language_list_columns("en");

    for (const element of _.range(0, formatted_list.length)) {
        assert.equal(formatted_list[element].name, successful_formatted_list[element].name);
        assert.equal(formatted_list[element].code, successful_formatted_list[element].code);
        assert.equal(
            formatted_list[element].name_with_percent,
            successful_formatted_list[element].name_with_percent,
        );
        assert.equal(formatted_list[element].selected, successful_formatted_list[element].selected);
    }
});
