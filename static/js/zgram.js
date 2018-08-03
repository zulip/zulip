var zgram = (function () {

var exports = {};

exports.send = function (opts) {
    var data = opts.data;

    channel.post({
        url: '/json/zgram',
        data: {
            data: JSON.stringify(data),
        },
    });
};

exports.handle_zgram_box = function (data) {
    /* TODOs:
        * Add schema checker.
        * Limit Number of button can be in a container, probably in schema checker
        * Remove mocked container with real container
    */

    var html = templates.render('image_button', {data: data.extra_data});
    var mock_container = $('<div></div>');
    mock_container.html(html);
};

exports.handle_event = function (event) {
    var data = event.data;
    if (data.widget_type === 'zgram_box') {
        exports.handle_zgram_box(data);
        return;
    }
};

/* TODO: In `Settings-> User Bots` we can add option for `/slash` command that
particular bot will listen to, so the a data structure of slash command
bots  will look somethink like `available_slash_command_bots` and maybe reside
in `bot_data`.

So `slash_command` would be an `model` field in db
*/

exports.available_slash_command_bots = [
    {
        username: 'giphy-bot@localhost',
        slash_command: '/giphy',
        bot_user_id: 26,
    },
];

exports.process = function (content) {
    var slash_command_found = _.some(exports.available_slash_command_bots, function (bot) {
        if (content.startsWith(bot.slash_command)) {
            var query = content.slice(bot.slash_command.length);
            var extra_data = {
                query: query,
            };

            var data = {
                content: content,
                target_user_id: bot.bot_user_id,
                extra_data: extra_data,
            };

            exports.send({
                data: data,
            });

            return true;
        }
    });

    return slash_command_found;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = zgram;
}

window.zgram = zgram;
