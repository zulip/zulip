"use strict";

const assert = require("node:assert/strict");

const {make_user} = require("./lib/example_user.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const bot_data = zrequire("bot_data");

const people = zrequire("people");

// Bot types and service bot types can be found
// in zerver/models/users.py - UserProfile Class or
// zever/openapi/zulip.yaml

const me = make_user({
    email: "me@zulip.com",
    full_name: "Me Myself",
    user_id: 2,
});

const fred = make_user({
    email: "fred@zulip.com",
    full_name: "Fred Frederickson",
    user_id: 3,
});

const bot_0_user = make_user({
    email: "bot0@zulip.com",
    full_name: "Bot 0",
    user_id: 42,
    is_bot: true,
    bot_type: 1, // DEFAULT_BOT
    bot_owner_id: 4,
});
const webhook_bot_user = make_user({
    email: "outgoingwebhook@zulip.com",
    full_name: "Outgoing webhook",
    user_id: 314,
    is_bot: true,
    bot_type: 3, // OUTGOING_WEBHOOK_BOT
    bot_owner_id: 5,
});
const test_bot_user = make_user({
    email: "bot1@zulip.com",
    full_name: "Bot 1",
    user_id: 43,
    // Default bot
    bot_type: 1,
    is_bot: true,
    bot_owner_id: 6,
});
const test_embedded_bot_user = make_user({
    email: "embedded-bot@zulip.com",
    full_name: "Embedded bot 1",
    user_id: 143,
    is_bot: true,
    bot_type: 4, // EMBEDDED_BOT
    bot_owner_id: 7,
});

const test_bot_1_user = make_user({
    email: "bot1@zulip.com",
    full_name: "Bot 1",
    user_id: 44,
    // Default bot
    bot_type: 1,
    is_bot: true,
    bot_owner_id: me.user_id,
});
const test_bot_2_user = make_user({
    email: "bot2@zulip.com",
    full_name: "Bot 1",
    user_id: 45,
    // Default bot
    bot_type: 1,
    is_bot: true,
    bot_owner_id: me.user_id,
});
const test_bot_3_user = make_user({
    email: "bot3@zulip.com",
    full_name: "Bot 1",
    user_id: 46,
    // Default bot
    bot_type: 1,
    is_bot: true,
    bot_owner_id: fred.user_id,
});

const bot_data_params = {
    realm_bots: [
        {
            default_all_public_streams: true,
            default_events_register_stream: "register stream 42",
            default_sending_stream: "sending stream 42",
            user_id: 42,
            services: [],
            extra: "This field should be ignored",
        },
        {
            default_all_public_streams: true,
            default_events_register_stream: "register stream 314",
            default_sending_stream: "sending stream 314",
            user_id: 314,
            services: [{base_url: "http://foo.com", interface: 1, token: "basictoken12345"}],
            extra: "This field should be ignored",
        },
    ],
};

function test(label, f) {
    run_test(label, ({override}) => {
        people.add_active_user(me);
        people.add_active_user(bot_0_user);
        people.add_active_user(webhook_bot_user);
        people.add_active_user(test_bot_user);
        people.add_active_user(test_embedded_bot_user);
        people.add_active_user(test_bot_1_user);
        people.add_active_user(test_bot_2_user);
        people.add_active_user(test_bot_3_user);
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
        default_all_public_streams: true,
        default_events_register_stream: "register stream 43",
        default_sending_stream: "sending stream 43",
        user_id: 43,
        services: [],
        extra: "This field should be ignored",
    };
    const test_embedded_bot = {
        default_all_public_streams: true,
        default_events_register_stream: "register stream 143",
        default_sending_stream: "sending stream 143",
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
        assert.equal(1, bot.bot_type);
        assert.equal(true, bot.default_all_public_streams);
        assert.equal("register stream 43", bot.default_events_register_stream);
        assert.equal("sending stream 43", bot.default_sending_stream);
        assert.equal("bot1@zulip.com", bot.email);
        assert.equal("Bot 1", bot.full_name);
        assert.equal(true, bot.is_active);
        assert.equal(6, bot.owner_id);
        assert.equal(43, bot.user_id);
        assert.equal(undefined, bot.extra);
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

    (function test_get_all_bots_for_current_user() {
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

test("get_all_bots_ids_for_current_user", () => {
    // Ensure bots owned by others are not included
    bot_data.add({
        default_all_public_streams: true,
        default_events_register_stream: "register stream test",
        default_sending_stream: "sending stream test",
        user_id: 44,
        services: [],
    });

    bot_data.add({
        default_all_public_streams: true,
        default_events_register_stream: "register stream another",
        default_sending_stream: "sending stream another",
        user_id: 46,
        services: [],
    });

    const my_bot_ids = bot_data.get_all_bots_ids_for_current_user();
    assert.deepEqual(my_bot_ids, [44]);
});
