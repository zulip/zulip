"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const bot_data = zrequire("bot_data");

const people = zrequire("people");

// Bot types and service bot types can be found
// in zerver/models.py - UserProfile Class or
// zever/openapi/zulip.yaml

const me = {
    email: "me@zulip.com",
    full_name: "Me Myself",
    user_id: 2,
};

const fred = {
    email: "fred@zulip.com",
    full_name: "Fred Frederickson",
    user_id: 3,
};

const bot_data_params = {
    realm_bots: [
        {
            api_key: "1234567890qwertyuioop",
            avatar_url: "",
            bot_type: 1, // DEFAULT_BOT
            default_all_public_streams: true,
            default_events_register_stream: "register stream 42",
            default_sending_stream: "sending stream 42",
            email: "bot0@zulip.com",
            full_name: "Bot 0",
            is_active: true,
            owner_id: 4,
            user_id: 42,
            services: [],
            extra: "This field should be ignored",
        },
        {
            api_key: "1234567890zxcvbnm",
            avatar_url: "",
            bot_type: 3, // OUTGOING_WEBHOOK_BOT
            default_all_public_streams: true,
            default_events_register_stream: "register stream 314",
            default_sending_stream: "sending stream 314",
            email: "outgoingwebhook@zulip.com",
            full_name: "Outgoing webhook",
            is_active: true,
            owner_id: 5,
            user_id: 314,
            services: [{base_url: "http://foo.com", interface: 1, token: "basictoken12345"}],
            extra: "This field should be ignored",
        },
    ],
};

function test(label, f) {
    run_test(label, ({override}) => {
        people.add_active_user(me);
        people.initialize_current_user(me.user_id);
        bot_data.initialize(bot_data_params);
        // Our startup logic should have added Bot 0 from page_params.
        assert.equal(bot_data.get(42).full_name, "Bot 0");
        assert.equal(bot_data.get(314).full_name, "Outgoing webhook");
        f({override});
    });
}

test("test_basics", () => {
    people.add_active_user(fred);
    const test_bot = {
        api_key: "qwertyuioop1234567890",
        avatar_url: "",
        bot_type: 1,
        default_all_public_streams: true,
        default_events_register_stream: "register stream 43",
        default_sending_stream: "sending stream 43",
        email: "bot1@zulip.com",
        full_name: "Bot 1",
        is_active: true,
        owner_id: 6,
        user_id: 43,
        services: [
            {
                base_url: "http://bar.com",
                interface: 1,
                token: "some Bot 1 token",
            },
        ],
        extra: "This field should be ignored",
    };
    const test_embedded_bot = {
        api_key: "zxcvbnm1234567890",
        avatar_url: "",
        bot_type: 4, // EMBEDDED_BOT
        default_all_public_streams: true,
        default_events_register_stream: "register stream 143",
        default_sending_stream: "sending stream 143",
        email: "embedded-bot@zulip.com",
        full_name: "Embedded bot 1",
        is_active: true,
        owner_id: 7,
        user_id: 143,
        services: [
            {
                config_data: {key: "12345678"},
                service_name: "giphy",
            },
        ],
        extra: "This field should be ignored",
    };

    (function test_add() {
        bot_data.add(test_bot);
        const bot = bot_data.get(43);
        const services = bot_data.get_services(43);
        assert.equal("qwertyuioop1234567890", bot.api_key);
        assert.equal("", bot.avatar_url);
        assert.equal(1, bot.bot_type);
        assert.equal(true, bot.default_all_public_streams);
        assert.equal("register stream 43", bot.default_events_register_stream);
        assert.equal("sending stream 43", bot.default_sending_stream);
        assert.equal("bot1@zulip.com", bot.email);
        assert.equal("Bot 1", bot.full_name);
        assert.equal(true, bot.is_active);
        assert.equal(6, bot.owner_id);
        assert.equal(43, bot.user_id);
        assert.equal("http://bar.com", services[0].base_url);
        assert.equal(1, services[0].interface);
        assert.equal("some Bot 1 token", services[0].token);
        assert.equal(undefined, bot.extra);
    })();

    (function test_update() {
        bot_data.add(test_bot);

        let bot = bot_data.get(43);
        assert.equal("Bot 1", bot.full_name);
        bot_data.update(43, {
            ...test_bot,
            full_name: "New Bot 1",
            services: [{interface: 2, base_url: "http://baz.com", token: "zxcvbnm1234567890"}],
        });
        bot = bot_data.get(43);
        const services = bot_data.get_services(43);
        assert.equal("New Bot 1", bot.full_name);
        assert.equal(2, services[0].interface);
        assert.equal("http://baz.com", services[0].base_url);
        assert.equal("zxcvbnm1234567890", services[0].token);

        const change_owner_event = {
            owner_id: fred.user_id,
        };
        bot_data.update(43, {...test_bot, ...change_owner_event});

        bot = bot_data.get(43);
        assert.equal(bot.owner_id, fred.user_id);
    })();

    (function test_embedded_bot_update() {
        bot_data.add(test_embedded_bot);
        const bot_id = 143;
        const services = bot_data.get_services(bot_id);
        assert.equal("12345678", services[0].config_data.key);
        bot_data.update(bot_id, {
            ...test_embedded_bot,
            services: [{config_data: {key: "87654321"}, service_name: "embedded bot service"}],
        });
        assert.equal("87654321", services[0].config_data.key);
        assert.equal("embedded bot service", services[0].service_name);
    })();

    (function test_remove() {
        let bot;

        bot_data.add({...test_bot, is_active: true});

        bot = bot_data.get(43);
        assert.equal("Bot 1", bot.full_name);
        assert.ok(bot.is_active);
        bot_data.deactivate(43);
        bot = bot_data.get(43);
        assert.equal(bot.is_active, false);
    })();

    (function test_all_user_ids() {
        const all_ids = bot_data.all_user_ids();
        all_ids.sort();
        assert.deepEqual(all_ids, [143, 314, 42, 43]);
    })();

    (function test_delete() {
        let bot;

        bot_data.add({...test_bot, is_active: true});

        bot = bot_data.get(43);
        assert.equal("Bot 1", bot.full_name);
        assert.ok(bot.is_active);
        bot_data.del(43);
        bot = bot_data.get(43);
        assert.equal(bot, undefined);
    })();

    (function test_get_editable() {
        bot_data.add({...test_bot, user_id: 44, owner_id: me.user_id, is_active: true});
        bot_data.add({
            ...test_bot,
            user_id: 45,
            email: "bot2@zulip.com",
            owner_id: me.user_id,
            is_active: true,
        });
        bot_data.add({
            ...test_bot,
            user_id: 46,
            email: "bot3@zulip.com",
            owner_id: fred.user_id,
            is_active: true,
        });

        const editable_bots = bot_data.get_editable().map((bot) => bot.email);
        assert.deepEqual(["bot1@zulip.com", "bot2@zulip.com"], editable_bots);
    })();

    (function test_get_all_bots_for_current_user() {
        const bots = bot_data.get_all_bots_for_current_user();

        assert.equal(bots.length, 2);
        assert.equal(bots[0].email, "bot1@zulip.com");
        assert.equal(bots[1].email, "bot2@zulip.com");
    })();

    (function test_get_number_of_bots_owned_by_user() {
        const bots_owned_by_user = bot_data.get_all_bots_owned_by_user(3);

        assert.equal(bots_owned_by_user[0].email, "bot3@zulip.com");
    })();
});
