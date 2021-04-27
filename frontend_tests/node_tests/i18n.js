"use strict";

const {strict: assert} = require("assert");

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

// All of our other tests stub out i18n activity;
// here we do a quick sanity check on the engine itself.
// `i18n.js` initializes FormatJS and is imported by
// `templates.js`.
unmock_module("../../static/js/i18n");
const {$t, $t_html} = zrequire("i18n");
zrequire("templates");

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
                id:
                    "<p>The stream <b>{stream_name}</b> does not exist.</p><p>Manage your subscriptions <z-link>on your Streams page</z-link>.</p>",
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
        topic: "testing",
    };

    const html = require("../../static/templates/actions_popover_content.hbs")(args);
    assert(html.indexOf("Citer et répondre ou transférer") > 0);
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
    assert(html.indexOf("Déclencheurs de notification") > 0);
});
