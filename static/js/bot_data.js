const bots = new Map();
const bot_fields = ['api_key', 'avatar_url', 'default_all_public_streams',
                    'default_events_register_stream', 'default_sending_stream',
                    'email', 'full_name', 'is_active', 'owner', 'bot_type', 'user_id'];
const services = new Map();
const services_fields = ['base_url', 'interface',
                         'config_data', 'service_name', 'token'];

const send_change_event = _.debounce(function () {
    settings_bots.render_bots();
}, 50);

const set_can_admin = function bot_data__set_can_admin(bot) {
    if (page_params.is_admin) {
        bot.can_admin = true;
    } else if (bot.owner !== undefined && people.is_current_user(bot.owner)) {
        bot.can_admin = true;
    } else {
        bot.can_admin = false;
    }
};

exports.add = function bot_data__add(bot) {
    const clean_bot = _.pick(bot, bot_fields);
    bots.set(bot.user_id, clean_bot);
    set_can_admin(clean_bot);
    const clean_services = bot.services.map(service => _.pick(service, services_fields));
    services.set(bot.user_id, clean_services);

    send_change_event();
};

exports.deactivate = function bot_data__deactivate(bot_id) {
    bots.get(bot_id).is_active = false;
    send_change_event();
};

exports.del = function bot_data__del(bot_id) {
    bots.delete(bot_id);
    services.delete(bot_id);
    send_change_event();
};

exports.update = function bot_data__update(bot_id, bot_update) {
    const bot = bots.get(bot_id);
    Object.assign(bot, _.pick(bot_update, bot_fields));
    set_can_admin(bot);

    // We currently only support one service per bot.
    const service = services.get(bot_id)[0];
    if (typeof bot_update.services !== 'undefined' && bot_update.services.length > 0) {
        Object.assign(service, _.pick(bot_update.services[0], services_fields));
    }
    send_change_event();
};

exports.get_all_bots_for_current_user = function bots_data__get_editable() {
    const ret = [];
    for (const bot of bots.values()) {
        if (people.is_current_user(bot.owner)) {
            ret.push(bot);
        }
    }
    return ret;
};

exports.get_editable = function bots_data__get_editable() {
    const ret = [];
    for (const bot of bots.values()) {
        if (bot.is_active && people.is_current_user(bot.owner)) {
            ret.push(bot);
        }
    }
    return ret;
};

exports.get = function bot_data__get(bot_id) {
    return bots.get(bot_id);
};

exports.get_bot_owner_email = function (bot_id) {
    return bots.get(bot_id).owner;
};

exports.get_services = function bot_data__get_services(bot_id) {
    return services.get(bot_id);
};

exports.initialize = function (params) {
    for (const bot of params.realm_bots) {
        exports.add(bot);
    }
};

window.bot_data = exports;
