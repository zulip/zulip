"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");

const {unmock_module, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

// We download our translations in `page_params` (which
// are for the user's chosen language), so we simulate
// that here for the tests.
page_params.request_language = "en";
page_params.translation_data = {
    "Quote message": "Citer le message",
    "Notification triggers": "Déclencheurs de notification",
    "You subscribed to channel {name}": "Vous n'êtes pas abonnés au canal {name}",
    "<p>The channel <b>{name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Channels page</z-link>.</p>":
        "<p>Le canal <b>{name}</b> n'existe pas.</p><p>Gérez vos abonnements <z-link>sur votre page canaux</z-link>.</p>",
};

// All of our other tests stub out i18n activity;
// here we do a quick sanity check on the engine itself.
// `i18n.ts` initializes FormatJS and is imported by
// `templates.ts`.
unmock_module("../src/i18n");
const {$t, $t_html, get_language_name, get_language_list_columns, initialize} = zrequire("i18n");

run_test("$t", () => {
    // Normally the id would be provided by babel-plugin-formatjs, but
    // this test file is not processed by Babel.
    assert.equal($t({id: "Quote message", defaultMessage: "Quote message"}), "Citer le message");
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
        should_display_quote_message: true,
        editability_menu_item: true,
        should_display_hide_option: true,
        conversation_time_url:
            "http://zulip.zulipdev.com/#narrow/channel/101-devel/topic/testing/near/99",
    };

    mock_template("popovers/message_actions_popover.hbs", true, (data, html) => {
        assert.equal(data, args);
        assert.ok(html.includes("Citer le message"));
    });

    require("../templates/popovers/message_actions_popover.hbs")(args);
});

run_test("{{#tr}} to tag for translation", ({mock_template}) => {
    const args = {
        notification_settings: {},
        settings_object: {},
        settings_label: {
            desktop_icon_count_display:
                "Unread count badge (appears in desktop sidebar and browser tab)",
            realm_name_in_email_notifications_policy:
                "Include organization name in subject of message notification emails",
            automatically_follow_topics_policy: "Automatically follow topics",
            automatically_unmute_topics_in_muted_streams_policy:
                "Automatically unmute topics in muted channels",
        },
    };

    // We're actually testing `notification_settings.hbs` here which
    // is imported as a partial in the file below. We want to test
    // the partial handling logic in `templates.ts`, that's why we
    // test the file below instead of directly testing
    // `notification_settings.hbs`.
    mock_template("settings/user_notification_settings.hbs", true, (data, html) => {
        assert.equal(data, args);
        assert.ok(html.includes("Déclencheurs de notification"));
    });
    require("../templates/settings/user_notification_settings.hbs")(args);
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
