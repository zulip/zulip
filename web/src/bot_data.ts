import type * as z from "zod/mini";

import type {services_schema} from "./bot_types.ts";
import {server_add_bot_schema, server_update_bot_schema} from "./bot_types.ts";
import * as people from "./people.ts";
import type {StateData} from "./state_data.ts";

export type ServerUpdateBotData = z.infer<typeof server_update_bot_schema>;
export type ServerAddBotData = z.infer<typeof server_add_bot_schema>;
export type Bot = Omit<ServerAddBotData, "services">;

export type Services = z.infer<typeof services_schema>;

const bots = new Map<number, Bot>();
const services = new Map<number, Services>();

export function all_user_ids(): number[] {
    return [...bots.keys()];
}

export function add(bot_data: ServerAddBotData): void {
    // TODO/typescript: Move validation to the caller when
    // server_events_dispatch.js is converted to TypeScript.
    const {services: bot_services, ...clean_bot} = server_add_bot_schema.parse(bot_data);
    bots.set(clean_bot.user_id, clean_bot);

    services.set(clean_bot.user_id, bot_services);
}

export function del(bot_id: number): void {
    bots.delete(bot_id);
    services.delete(bot_id);
}

export function update(bot_id: number, bot_update: ServerUpdateBotData): void {
    const bot = bots.get(bot_id)!;
    // TODO/typescript: Move validation to the caller when
    // server_events_dispatch.js is converted to TypeScript.
    const {services: services_update, ...bot_update_rest} =
        server_update_bot_schema.parse(bot_update);

    Object.assign(bot, bot_update_rest);

    // We currently only support one service per bot.
    const service = services.get(bot_id)![0];
    if (service !== undefined && services_update !== undefined && services_update.length > 0) {
        Object.assign(service, services_update[0]);
    }
}

export function get_all_bots_for_current_user(): Bot[] {
    const ret = [];
    for (const bot of bots.values()) {
        if (bot.owner_id !== null && people.is_my_user_id(bot.owner_id)) {
            ret.push(bot);
        }
    }
    return ret;
}

export function get_all_bots_owned_by_user(user_id: number): Bot[] {
    const ret = [];
    for (const bot of bots.values()) {
        if (bot.owner_id === user_id && bot.is_active) {
            ret.push(bot);
        }
    }
    return ret;
}

export function get(bot_id: number): Bot | undefined {
    return bots.get(bot_id);
}

export function get_services(bot_id: number): Services | undefined {
    return services.get(bot_id);
}

export function initialize(params: StateData["bot"]): void {
    bots.clear();
    for (const bot of params.realm_bots) {
        add(bot);
    }
}
