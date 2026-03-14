"use strict";

const assert = require("node:assert/strict");

const {make_realm} = require("./lib/example_realm.cjs");
const {make_user} = require("./lib/example_user.cts");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

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
