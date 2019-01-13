var _settings_bots = {
    render_bots: () => {},
};

const _page_params = {
    realm_bots: [{email: 'bot0@zulip.com', user_id: 42, full_name: 'Bot 0'},
                 {email: 'outgoingwebhook@zulip.com', user_id: 314, full_name: "Outgoing webhook",
                  services: [{base_url: "http://foo.com", interface: 1}]}],
    is_admin: false,
};

set_global('page_params', _page_params);
set_global('settings_bots', _settings_bots);

zrequire('people');
zrequire('bot_data');

global.people.add({
    email: 'owner@zulip.com',
    full_name: 'The Human Boss',
    user_id: 42,
});

global.people.initialize_current_user(42);

bot_data.initialize();
// Our startup logic should have added Bot 0 from page_params.
assert.equal(bot_data.get(42).full_name, 'Bot 0');
assert.equal(bot_data.get(314).full_name, 'Outgoing webhook');

run_test('test_basics', () => {
    const test_bot = {
        email: 'bot1@zulip.com',
        user_id: 43,
        avatar_url: '',
        full_name: 'Bot 1',
        services: [{base_url: "http://bar.com", interface: 1}],
        extra: 'Not in data',
    };

    const test_embedded_bot = {
        email: 'embedded-bot@zulip.com',
        user_id: 143,
        avatar_url: '',
        full_name: 'Embedded bot 1',
        services: [{config_data: {key: '12345678'},
                    service_name: "giphy"}],
        owner: 'cordelia@zulip.com',
    };

    (function test_add() {
        bot_data.add(test_bot);

        const bot = bot_data.get(43);
        const services = bot_data.get_services(43);
        assert.equal('Bot 1', bot.full_name);
        assert.equal('http://bar.com', services[0].base_url);
        assert.equal(1, services[0].interface);
        assert.equal(undefined, bot.extra);
    }());

    (function test_update() {
        bot_data.add(test_bot);

        let bot = bot_data.get(43);
        assert.equal('Bot 1', bot.full_name);
        bot_data.update(43, {full_name: 'New Bot 1',
                             services: [{interface: 2,
                                         base_url: 'http://baz.com'}]});
        bot = bot_data.get(43);
        const services = bot_data.get_services(43);
        assert.equal('New Bot 1', bot.full_name);
        assert.equal(2, services[0].interface);
        assert.equal('http://baz.com', services[0].base_url);
    }());

    (function test_embedded_bot_update() {
        bot_data.add(test_embedded_bot);
        const bot_id = 143;
        const services = bot_data.get_services(bot_id);
        assert.equal('12345678', services[0].config_data.key);
        bot_data.update(bot_id, {services: [{config_data: {key: '87654321'}}]});
        assert.equal('87654321', services[0].config_data.key);
    }());

    (function test_remove() {
        let bot;

        bot_data.add({ ...test_bot, is_active: true });

        bot = bot_data.get(43);
        assert.equal('Bot 1', bot.full_name);
        assert(bot.is_active);
        bot_data.deactivate(43);
        bot = bot_data.get(43);
        assert.equal(bot.is_active, false);
    }());

    (function test_delete() {
        let bot;

        bot_data.add({ ...test_bot, is_active: true });

        bot = bot_data.get(43);
        assert.equal('Bot 1', bot.full_name);
        assert(bot.is_active);
        bot_data.delete(43);
        bot = bot_data.get(43);
        assert.equal(bot, undefined);
    }());

    (function test_owner_can_admin() {
        let bot;

        bot_data.add({owner: 'owner@zulip.com', ...test_bot});

        bot = bot_data.get(43);
        assert(bot.can_admin);

        bot_data.add({owner: 'notowner@zulip.com', ...test_bot});

        bot = bot_data.get(43);
        assert.equal(false, bot.can_admin);
    }());

    (function test_admin_can_admin() {
        page_params.is_admin = true;

        bot_data.add(test_bot);

        const bot = bot_data.get(43);
        assert(bot.can_admin);

        page_params.is_admin = false;
    }());

    (function test_get_editable() {
        let can_admin;

        bot_data.add({...test_bot, user_id: 44, owner: 'owner@zulip.com', is_active: true});
        bot_data.add({...test_bot, user_id: 45, email: 'bot2@zulip.com', owner: 'owner@zulip.com', is_active: true});
        bot_data.add({...test_bot, user_id: 46, email: 'bot3@zulip.com', owner: 'not_owner@zulip.com', is_active: true});

        can_admin = _.pluck(bot_data.get_editable(), 'email');
        assert.deepEqual(['bot1@zulip.com', 'bot2@zulip.com'], can_admin);

        page_params.is_admin = true;

        can_admin = _.pluck(bot_data.get_editable(), 'email');
        assert.deepEqual(['bot1@zulip.com', 'bot2@zulip.com'], can_admin);
    }());

    (function test_get_all_bots_for_current_user() {
        const bots = bot_data.get_all_bots_for_current_user();

        assert.equal(bots.length, 2);
        assert.equal(bots[0].email, 'bot1@zulip.com');
        assert.equal(bots[1].email, 'bot2@zulip.com');
    }());

    (function test_get_bot_owner_email() {
        let bot_owner_email = bot_data.get_bot_owner_email(test_embedded_bot.user_id);
        assert.equal('cordelia@zulip.com', bot_owner_email);
        bot_owner_email = bot_data.get_bot_owner_email(test_bot.user_id);
        assert.equal(undefined, bot_owner_email);
    }());
});
