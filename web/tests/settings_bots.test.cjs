"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const channel = mock_esm("../src/channel", {post: noop});
mock_esm("../src/buttons", {
    show_button_loading_indicator: noop,
    hide_button_loading_indicator: noop,
});

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

test("regenerate_bot_api_key_inline_confirmation", () => {
    bot_helper.initialize_bot_click_handlers();

    const $container = $.create("bot-api-key-container-stub");
    $container.attr("data-user-id", "1");

    const $regenerate_button = $(".regenerate-button-stub");
    const $cancel_button = $(".cancel-button-stub");
    const $confirm_button = $(".confirm-button-stub");
    const $copy_button = $(".copy-button-stub");
    const $warning = $.create("regenerate-warning-stub");
    $cancel_button.addClass("hide");
    $confirm_button.addClass("hide");
    $warning.addClass("hide");

    $regenerate_button.set_closest_results(".bot-api-key-container", $container);
    $cancel_button.set_closest_results(".bot-api-key-container", $container);
    $confirm_button.set_closest_results(".bot-api-key-container", $container);
    $container.set_find_results(".bot-modal-regenerate-bot-api-key", $regenerate_button);
    $container.set_find_results(".bot-modal-cancel-regenerate-bot-api-key", $cancel_button);
    $container.set_find_results(".bot-modal-confirm-regenerate-bot-api-key", $confirm_button);
    $container.set_find_results(".copy-api-key", $copy_button);
    $container.set_find_results(".bot-api-key-regenerate-warning", $warning);

    const $api_key_input = $.create("api-key-input-stub");
    const $error = $.create("api-key-error-stub");
    $container.set_find_results(".api-key", $api_key_input);
    $container.set_find_results(".bot-modal-api-key-error", $error);

    let post_opts;
    channel.post = (opts) => {
        post_opts = opts;
    };

    const regenerate_handler = $("body").get_on_handler(
        "click",
        "button.bot-modal-regenerate-bot-api-key",
    );
    const cancel_handler = $("body").get_on_handler(
        "click",
        "button.bot-modal-cancel-regenerate-bot-api-key",
    );
    const confirm_handler = $("body").get_on_handler(
        "click",
        "button.bot-modal-confirm-regenerate-bot-api-key",
    );

    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});

    assert.equal(post_opts, undefined);
    assert.ok($regenerate_button.hasClass("hide"));
    assert.ok($copy_button.hasClass("hide"));
    assert.ok(!$cancel_button.hasClass("hide"));
    assert.ok(!$confirm_button.hasClass("hide"));
    assert.ok(!$warning.hasClass("hide"));
    // Focus lands on Cancel, not Confirm, so a second Enter or double-click backs out.
    assert.ok($cancel_button.is_focused());
    assert.ok(!$confirm_button.is_focused());
    cancel_handler({preventDefault: noop, currentTarget: ".cancel-button-stub"});
    assert.equal(post_opts, undefined);
    assert.ok(!$regenerate_button.hasClass("hide"));
    assert.ok(!$copy_button.hasClass("hide"));
    assert.ok($cancel_button.hasClass("hide"));
    assert.ok($confirm_button.hasClass("hide"));
    assert.ok($warning.hasClass("hide"));
    assert.ok($regenerate_button.is_focused());

    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});
    confirm_handler.call(".confirm-button-stub", {preventDefault: noop});
    assert.equal(post_opts.url, "/json/bots/1/api_key/regenerate");
    assert.ok($cancel_button.hasClass("hide"));

    post_opts.success({api_key: "new-api-key"});
    post_opts.complete();
    assert.equal($api_key_input.val(), "new-api-key");
    assert.equal($container.attr("data-api-key"), "new-api-key");
    assert.ok(!$regenerate_button.hasClass("hide"));
    assert.ok(!$copy_button.hasClass("hide"));
    assert.ok($cancel_button.hasClass("hide"));
    assert.ok($confirm_button.hasClass("hide"));
    assert.ok($warning.hasClass("hide"));

    // A crafted server error message is shown below the key; this one is
    // what access_bot_by_id raises when the owner loses permission for
    // the bot between opening the modal and confirming.
    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});
    confirm_handler.call(".confirm-button-stub", {preventDefault: noop});
    post_opts.error({status: 400, responseJSON: {msg: "Insufficient permission"}});
    post_opts.complete();
    assert.equal($error.text(), "Insufficient permission");
    assert.ok($error.visible());

    // A failure without a JSON body (network failure, or a proxy-level
    // 502 during a server restart) must still surface a generic error
    // rather than failing silently.
    regenerate_handler({preventDefault: noop, currentTarget: ".regenerate-button-stub"});
    confirm_handler.call(".confirm-button-stub", {preventDefault: noop});
    post_opts.error({status: 0});
    post_opts.complete();
    assert.equal($error.text(), "translated: Failed to generate new API key");
    assert.ok($error.visible());
    assert.ok(!$regenerate_button.hasClass("hide"));
    assert.ok($confirm_button.hasClass("hide"));
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
