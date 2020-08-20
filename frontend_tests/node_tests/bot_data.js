"use strict";

const _settings_bots = {
    render_bots: () => {},
};

set_global("settings_bots", _settings_bots);

zrequire("bot_data");
const people = zrequire("people");

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

people.add_active_user(me);
people.add_active_user(fred);
people.initialize_current_user(me.user_id);

const bot_data_params = {
    realm_bots: [
        {email: "bot0@zulip.com", user_id: 42, full_name: "Bot 0", services: []},
        {
            email: "outgoingwebhook@zulip.com",
            user_id: 314,
            full_name: "Outgoing webhook",
            services: [{base_url: "http://foo.com", interface: 1}],
        },
    ],
};

bot_data.initialize(bot_data_params);
// Our startup logic should have added Bot 0 from page_params.
assert.equal(bot_data.get(42).full_name, "Bot 0");
assert.equal(bot_data.get(314).full_name, "Outgoing webhook");

run_test("test_basics", () => {
    const test_bot = {
        email: "bot1@zulip.com",
        user_id: 43,
        avatar_url: "",
        full_name: "Bot 1",
        services: [{base_url: "http://bar.com", interface: 1}],
        extra: "Not in data",
    };

    const test_embedded_bot = {
        email: "embedded-bot@zulip.com",
        user_id: 143,
        avatar_url: "",
        full_name: "Embedded bot 1",
        services: [{config_data: {key: "12345678"}, service_name: "giphy"}],
        owner: "cordelia@zulip.com",
    };

    (function test_add() {
        bot_data.add(test_bot);

        const bot = bot_data.get(43);
        const services = bot_data.get_services(43);
        assert.equal("Bot 1", bot.full_name);
        assert.equal("http://bar.com", services[0].base_url);
        assert.equal(1, services[0].interface);
        assert.equal(undefined, bot.extra);
    })();

    (function test_update() {
        bot_data.add(test_bot);

        let bot = bot_data.get(43);
        assert.equal("Bot 1", bot.full_name);
        bot_data.update(43, {
            full_name: "New Bot 1",
            services: [{interface: 2, base_url: "http://baz.com"}],
        });
        bot = bot_data.get(43);
        const services = bot_data.get_services(43);
        assert.equal("New Bot 1", bot.full_name);
        assert.equal(2, services[0].interface);
        assert.equal("http://baz.com", services[0].base_url);

        const change_owner_event = {
            owner_id: fred.user_id,
        };
        bot_data.update(43, change_owner_event);

        bot = bot_data.get(43);
        assert.equal(bot.owner_id, fred.user_id);
    })();

    (function test_embedded_bot_update() {
        bot_data.add(test_embedded_bot);
        const bot_id = 143;
        const services = bot_data.get_services(bot_id);
        assert.equal("12345678", services[0].config_data.key);
        bot_data.update(bot_id, {services: [{config_data: {key: "87654321"}}]});
        assert.equal("87654321", services[0].config_data.key);
    })();

    (function test_remove() {
        let bot;

        bot_data.add({...test_bot, is_active: true});

        bot = bot_data.get(43);
        assert.equal("Bot 1", bot.full_name);
        assert(bot.is_active);
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
        assert(bot.is_active);
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
});
