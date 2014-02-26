set_global('$', function () {});

var bot_data = require('js/bot_data.js');

(function () {
    var test_bot = {
        email: 'bot1@zulip.com',
        avatar_url: '',
        default_all_public_streams: '',
        default_events_register_stream: '',
        default_sending_stream: '',
        full_name: 'Bot 1',
        extra: 'Not in data'
    };

    (function test_add() {
        bot_data.add(test_bot);

        var bot = bot_data.get('bot1@zulip.com');
        assert.equal('Bot 1', bot.full_name);
        assert.equal(undefined, bot.extra);
    }());

    (function test_update() {
        var bot;

        bot_data.add(test_bot);

         bot = bot_data.get('bot1@zulip.com');
        assert.equal('Bot 1', bot.full_name);
        bot_data.update('bot1@zulip.com', {full_name: 'New Bot 1'});
        bot = bot_data.get('bot1@zulip.com');
        assert.equal('New Bot 1', bot.full_name);
    }());

    (function test_remove() {
        var bot;

        bot_data.add(test_bot);

        bot = bot_data.get('bot1@zulip.com');
        assert.equal('Bot 1', bot.full_name);
        bot_data.remove('bot1@zulip.com');
        bot = bot_data.get('bot1@zulip.com');
        assert.equal(undefined, bot);
    }());

}());
