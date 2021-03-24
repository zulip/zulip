import _ from "lodash";

import * as people from "./people";

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

export function all_user_ids() {
    return Array.from(bots.keys());
}

export function add(bot) {
    const clean_bot = _.pick(bot, bot_fields);
    bots.set(bot.user_id, clean_bot);
    const clean_services = bot.services.map((service) => _.pick(service, services_fields));
    services.set(bot.user_id, clean_services);
}

export function deactivate(bot_id) {
    bots.get(bot_id).is_active = false;
}

export function del(bot_id) {
    bots.delete(bot_id);
    services.delete(bot_id);
}

export function update(bot_id, bot_update) {
    const bot = bots.get(bot_id);
    Object.assign(bot, _.pick(bot_update, bot_fields));

    // We currently only support one service per bot.
    const service = services.get(bot_id)[0];
    if (bot_update.services !== undefined && bot_update.services.length > 0) {
        Object.assign(service, _.pick(bot_update.services[0], services_fields));
    }
}

export function get_all_bots_for_current_user() {
    const ret = [];
    for (const bot of bots.values()) {
        if (people.is_my_user_id(bot.owner_id)) {
            ret.push(bot);
        }
    }
    return ret;
}

export function get_editable() {
    const ret = [];
    for (const bot of bots.values()) {
        if (bot.is_active && people.is_my_user_id(bot.owner_id)) {
            ret.push(bot);
        }
    }
    return ret;
}

export function get(bot_id) {
    return bots.get(bot_id);
}

export function get_services(bot_id) {
    return services.get(bot_id);
}

export function initialize(params) {
    bots.clear();
    for (const bot of params.realm_bots) {
        add(bot);
    }
}
