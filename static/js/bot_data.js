/* eslint indent: "off" */

var bot_data = (function () {
    var exports = {};

    var bots = {};
    var bot_fields = ['api_key', 'avatar_url', 'default_all_public_streams',
                      'default_events_register_stream', 'default_sending_stream',
                      'email', 'full_name', 'is_active', 'owner', 'bot_type', 'user_id'];
    var services = {};
    var services_fields = ['base_url', 'interface',
                           'config_data', 'service_name', 'token'];

    var send_change_event = _.debounce(function () {
        settings_bots.render_bots();
    }, 50);

    var set_can_admin = function bot_data__set_can_admin(bot) {
        if (page_params.is_admin) {
            bot.can_admin = true;
        } else if (bot.owner !== undefined && people.is_current_user(bot.owner)) {
            bot.can_admin = true;
        } else {
            bot.can_admin = false;
        }
    };

    exports.add = function bot_data__add(bot) {
        var clean_bot = _.pick(bot, bot_fields);
        bots[bot.user_id] = clean_bot;
        set_can_admin(clean_bot);
        var clean_services = _.map(bot.services, function (service) {
            return _.pick(service, services_fields);
        });
        services[bot.user_id] = clean_services;

        send_change_event();
    };

    exports.deactivate = function bot_data__deactivate(bot_id) {
        bots[bot_id].is_active = false;
        send_change_event();
    };

    exports.delete = function bot_data__delete(bot_id) {
        delete bots[bot_id];
        delete services[bot_id];
        send_change_event();
    };

    exports.update = function bot_data__update(bot_id, bot_update) {
        var bot = bots[bot_id];
        _.extend(bot, _.pick(bot_update, bot_fields));
        set_can_admin(bot);

        // We currently only support one service per bot.
        var service = services[bot_id][0];
        if (typeof bot_update.services !== 'undefined' && bot_update.services.length > 0) {
            _.extend(service, _.pick(bot_update.services[0], services_fields));
        }
        send_change_event();
    };

    exports.get_all_bots_for_current_user = function bots_data__get_editable() {
        return _.filter(bots, function (bot) {
            return people.is_current_user(bot.owner);
        });
    };

    exports.get_editable = function bots_data__get_editable() {
        return _.filter(bots, function (bot) {
            return bot.is_active && people.is_current_user(bot.owner);
        });
    };

    exports.get = function bot_data__get(bot_id) {
        return bots[bot_id];
    };

    exports.get_bot_owner_email = function (bot_id) {
        return bots[bot_id].owner;
    };

    exports.get_services = function bot_data__get_services(bot_id) {
        return services[bot_id];
    };

    exports.initialize = function () {
        _.each(page_params.realm_bots, function (bot) {
            exports.add(bot);
        });
        delete page_params.realm_bots;
    };

    return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = bot_data;
}
window.bot_data = bot_data;
