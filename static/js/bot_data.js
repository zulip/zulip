"use strict";

const _ = require("lodash");

const people = require("./people");

const bots = new Map();

const bot_fields = [
    "api_key",
    "avatar_url",
    "bot_type",
    "default_all_public_streams",
    "default_events_register_stream",
    "default_sending_stream",
    "email",
    "full_name",
    "is_active",
    "owner", // TODO: eliminate
    "owner_id",
    "user_id",
];

const services = new Map();
const services_fields = ["base_url", "interface", "config_data", "service_name", "token"];

const send_change_event = _.debounce(() => {
    settings_bots.render_bots();
}, 50);

exports.all_user_ids = function () {
    return Array.from(bots.keys());
};

exports.add = function (bot) {
    const clean_bot = _.pick(bot, bot_fields);
    bots.set(bot.user_id, clean_bot);
    const clean_services = bot.services.map((service) => _.pick(service, services_fields));
    services.set(bot.user_id, clean_services);

    send_change_event();
};

exports.deactivate = function (bot_id) {
    bots.get(bot_id).is_active = false;
    send_change_event();
};

exports.del = function (bot_id) {
    bots.delete(bot_id);
    services.delete(bot_id);
    send_change_event();
};

exports.update = function (bot_id, bot_update) {
    const bot = bots.get(bot_id);
    Object.assign(bot, _.pick(bot_update, bot_fields));

    // We currently only support one service per bot.
    const service = services.get(bot_id)[0];
    if (typeof bot_update.services !== "undefined" && bot_update.services.length > 0) {
        Object.assign(service, _.pick(bot_update.services[0], services_fields));
    }

    send_change_event();
};

exports.get_all_bots_for_current_user = function () {
    const ret = [];
    for (const bot of bots.values()) {
        if (people.is_my_user_id(bot.owner_id)) {
            ret.push(bot);
        }
    }
    return ret;
};

exports.get_editable = function () {
    const ret = [];
    for (const bot of bots.values()) {
        if (bot.is_active && people.is_my_user_id(bot.owner_id)) {
            ret.push(bot);
        }
    }
    return ret;
};

exports.get = function (bot_id) {
    return bots.get(bot_id);
};

exports.get_services = function (bot_id) {
    return services.get(bot_id);
};

exports.initialize = function (params) {
    for (const bot of params.realm_bots) {
        exports.add(bot);
    }
};

window.bot_data = exports;
