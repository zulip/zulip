import {z} from "zod";

import * as people from "./people";

export type ServerUpdateBotData = z.infer<typeof server_update_bot_schema>;
export type ServerAddBotData = z.infer<typeof server_add_bot_schema>;
export type Bot = Omit<ServerAddBotData, "services">;

export type Services = z.infer<typeof services_schema>;

export type BotDataParams = {
    realm_bots: ServerAddBotData[];
};

const bots = new Map<number, Bot>();
const services = new Map<number, Services>();

// Define zod schema for data validation
const basic_bot_schema = z.object({
    api_key: z.string(),
    avatar_url: z.string(),
    bot_type: z.number(),
    default_all_public_streams: z.boolean(),
    default_events_register_stream: z.union([z.string(), z.null()]),
    default_sending_stream: z.union([z.string(), z.null()]),
    email: z.string(),
    full_name: z.string(),
    is_active: z.boolean(),
    owner_id: z.number().nullable(),
    user_id: z.number(),
});

const outgoing_service_schema = z.object({
    base_url: z.string(),
    interface: z.number(),
    token: z.string(),
});

const embedded_service_schema = z.object({
    config_data: z.record(z.string()),
    service_name: z.string(),
});

const services_schema = z.union([
    z.array(outgoing_service_schema),
    z.array(embedded_service_schema),
]);

const server_update_bot_schema = basic_bot_schema.extend({
    services: services_schema,
});

const server_add_bot_schema = server_update_bot_schema.extend({
    bot_type: z.number(),
    email: z.string(),
    is_active: z.boolean(),
});

export function all_user_ids(): number[] {
    return [...bots.keys()];
}

export function add(bot_data: ServerAddBotData): void {
    const {services: bot_services, ...clean_bot} = server_add_bot_schema.parse(bot_data);
    bots.set(clean_bot.user_id, clean_bot);

    services.set(clean_bot.user_id, bot_services);
}

export function deactivate(bot_id: number): void {
    bots.get(bot_id)!.is_active = false;
}

export function del(bot_id: number): void {
    bots.delete(bot_id);
    services.delete(bot_id);
}

export function update(bot_id: number, bot_update: ServerUpdateBotData): void {
    const bot = bots.get(bot_id)!;
    Object.assign(bot, server_update_bot_schema.deepPartial().parse(bot_update));

    // We currently only support one service per bot.
    const service = services.get(bot_id)![0];
    if (bot_update.services !== undefined && bot_update.services.length > 0) {
        Object.assign(service, services_schema.parse(bot_update.services)[0]);
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

export function get_editable(): Bot[] {
    const ret = [];
    for (const bot of bots.values()) {
        if (bot.is_active && bot.owner_id !== null && people.is_my_user_id(bot.owner_id)) {
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

export function initialize(params: BotDataParams): void {
    bots.clear();
    for (const bot of params.realm_bots) {
        add(bot);
    }
}
