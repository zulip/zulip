"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {$} = require("./lib/zjquery.cjs");

const banners = mock_esm("../src/banners");
const buttons = mock_esm("../src/buttons");
const channel = mock_esm("../src/channel");

const bot_data = zrequire("bot_data");
const bot_helper = zrequire("bot_helper");
const people = zrequire("people");
const settings_bots = zrequire("settings_bots");
const {set_current_user, set_realm} = zrequire("state_data");

const bot_user = make_user({
    email: "error-bot@zulip.org",
    full_name: "Error bot",
    user_id: 1,
    is_bot: true,
    bot_type: 1, // DEFAULT_BOT
    owner_id: 4,
});
people.add_active_user(bot_user);

const bot_api_key = "QadL788EkiottHmukyhHgePUFHREiu8b";
const bot_data_params = {
    realm_bots: [
        {
            default_all_public_streams: true,
            default_events_register_stream: "register stream 1",
            default_sending_stream: "sending stream 1",
            user_id: 1,
            services: [],
            extra: "This field should be ignored",
        },
    ],
};

const current_user = {};
set_current_user(current_user);
const realm = make_realm();
set_realm(realm);

bot_data.initialize(bot_data_params);

function test(label, f) {
    run_test(label, ({override}) => {
        override(realm, "realm_url", "https://chat.example.com");
        override(realm, "realm_embedded_bots", [
            {name: "converter", config: {}},
            {name: "giphy", config: {key: "12345678"}},
            {name: "foobot", config: {bar: "baz", qux: "quux"}},
        ]);

        f({override});
    });
}

test("generate_zuliprc_url", () => {
    const url = bot_helper.generate_zuliprc_url(1, bot_api_key);
    const expected =
        "data:application/octet-stream;charset=utf-8," +
        encodeURIComponent(
            "[api]\nemail=error-bot@zulip.org\n" +
                "key=QadL788EkiottHmukyhHgePUFHREiu8b\n" +
                "site=https://chat.example.com\n",
        );

    assert.equal(url, expected);
});

test("generate_zuliprc_content", () => {
    const bot_user = bot_data.get(1);
    const content = bot_helper.generate_zuliprc_content({...bot_user, api_key: bot_api_key});
    const expected =
        "[api]\nemail=error-bot@zulip.org\n" +
        "key=QadL788EkiottHmukyhHgePUFHREiu8b\n" +
        "site=https://chat.example.com\n";

    assert.equal(content, expected);
});

test("regenerate_bot_api_key_confirmation_banner", ({override}) => {
    bot_helper.initialize_bot_click_handlers();

    const $container = $.create("bot-api-key-container-stub");
    $container.attr("data-user-id", "1");

    const $regenerate_button = $(".regenerate-button-stub");
    const $cancel_button = $(".cancel-stub");
    const $confirm_button = $(".confirm-stub");
    $regenerate_button.set_closest_results(".bot-api-key-container", $container);
    $cancel_button.set_closest_results(".bot-api-key-container", $container);
    $confirm_button.set_closest_results(".bot-api-key-container", $container);

    const $api_key_input = $.create("api-key-input-stub");
    const $error = $.create("api-key-error-stub");
    const $banner = $.create("regenerate-banner-stub");
    $container.set_find_results(".bot-modal-regenerate-bot-api-key", $regenerate_button);
    $container.set_find_results(".bot-modal-cancel-regenerate-bot-api-key", $cancel_button);
    $container.set_find_results(".api-key", $api_key_input);
    $container.set_find_results(".bot-modal-api-key-error", $error);
    $container.set_find_results(
        ".bot-api-key-regenerate-banner",
        $.create("regenerate-banner-container-stub"),
    );
    $container.set_find_results(".bot-api-key-regenerate-banner .banner", $banner);

    let opened_banner;
    override(banners, "open", (banner) => {
        opened_banner = banner;
        return $banner;
    });
    let $closed_banner;
    override(banners, "close", ($banner_to_close) => {
        $closed_banner = $banner_to_close;
    });
    override(buttons, "show_button_loading_indicator", noop);

    let post_opts;
    override(channel, "post", (opts) => {
        post_opts = opts;
    });
    override(
        channel,
        "xhr_error_message",
        (message_html, xhr) => `${message_html} (status ${xhr.status})`,
    );

    const regenerate_handler = $("body").get_on_handler(
        "click",
        "button.bot-modal-regenerate-bot-api-key",
    );

    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});
    assert.equal(post_opts, undefined);
    assert.equal(opened_banner.intent, "warning");
    assert.ok($cancel_button.is_focused());

    const [confirm_button] = opened_banner.buttons;
    // Confirm describes itself with the banner's own warning text, so the
    // consequences are announced when focus reaches it. Cancel gets focus
    // first but lives in the template, which is handed the same id; a typo
    // there would silently render no attribute at all.
    assert.equal(confirm_button["aria-describedby"], opened_banner.label_id);
    const rendered_api_key_details = require("../templates/settings/bot_api_key_details.hbs")({
        bot_id: 1,
        api_key: "api-key",
        regenerate_warning_id: opened_banner.label_id,
    });
    assert.ok(rendered_api_key_details.includes(`aria-describedby="${opened_banner.label_id}"`));
    const cancel_handler = $("body").get_on_handler(
        "click",
        "button.bot-modal-cancel-regenerate-bot-api-key",
    );
    const confirm_handler = $("body").get_on_handler(
        "click",
        `button.${confirm_button.custom_classes}`,
    );

    cancel_handler({preventDefault: noop, currentTarget: ".cancel-stub"});
    assert.equal(post_opts, undefined);
    assert.equal($closed_banner[0], $banner[0]);
    assert.ok($regenerate_button.is_focused());

    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});
    confirm_handler.call(".confirm-stub", {preventDefault: noop});
    assert.equal(post_opts.url, "/json/bots/1/api_key/regenerate");

    post_opts.success({api_key: "new-api-key"});
    assert.equal($api_key_input.val(), "new-api-key");
    assert.equal($container.attr("data-api-key"), "new-api-key");
    assert.equal($closed_banner[0], $banner[0]);

    // A failed rotation backs out of the confirmation and reports why below
    // the key; a 403 is what access_bot_by_id raises when the owner loses
    // permission for the bot between opening the modal and confirming.
    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});
    confirm_handler.call(".confirm-stub", {preventDefault: noop});
    post_opts.error({status: 403, responseJSON: {msg: "Insufficient permission"}});
    assert.equal($error.html(), "translated: Failed to generate new API key (status 403)");
    assert.ok($error.visible());
    assert.equal($closed_banner[0], $banner[0]);

    // Asking to rotate again clears the stale error from the failed attempt.
    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});
    assert.ok(!$error.visible());

    confirm_handler.call(".confirm-stub", {preventDefault: noop});
    blueslip.expect("error", "Unexpected response to bot API key regeneration");
    post_opts.success({});
    assert.equal($error.html(), "translated: Failed to generate new API key");
    assert.ok($error.visible());
    assert.equal($api_key_input.val(), "new-api-key");
});

test("generate_botserverrc_content", () => {
    const user = {
        email: "vabstest-bot@zulip.com",
        api_key: "nSlA0mUm7G42LP85lMv7syqFTzDE2q34",
    };
    const service = {
        token: "abcd1234",
    };
    const content = settings_bots.generate_botserverrc_content(
        user.email,
        user.api_key,
        service.token,
    );
    const expected =
        "[]\nemail=vabstest-bot@zulip.com\n" +
        "key=nSlA0mUm7G42LP85lMv7syqFTzDE2q34\n" +
        "site=https://chat.example.com\n" +
        "token=abcd1234\n";

    assert.equal(content, expected);
});
