var bot_data = (function () {
    var exports = {};

    var bots = {};
    var bot_fields = ['api_key', 'avatar_url', 'default_all_public_streams',
                      'default_events_register_stream',
                      'default_sending_stream', 'email', 'full_name'];

    exports.add = function bot_data__add(bot) {
        bots[bot.email] = _.pick(bot, bot_fields);
    };

    exports.remove = function bot_data__remove(email) {
        delete bots[email];
    };

    exports.update = function bot_data__update(email, bot_update) {
        _.extend(bots[email], _.pick(bot_update, bot_fields));
    };

    exports.get_all = function bots_data__get_all() {
        return bots;
    };

    exports.get = function bots_data__get(email) {
        return bots[email];
    };

    $(function init() {
        _.each(page_params.bot_list, function (bot) {
            exports.add(bot);
        });
    });

    return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = bot_data;
}
