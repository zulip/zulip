import {z} from "zod";

const basic_bot_schema = z.object({
    api_key: z.string(),
    avatar_url: z.string(),
    bot_type: z.number(),
    default_all_public_streams: z.boolean(),
    default_events_register_stream: z.string().nullable(),
    default_sending_stream: z.string().nullable(),
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

export const services_schema = z.union([
    z.array(outgoing_service_schema),
    z.array(embedded_service_schema),
]);

export const server_update_bot_schema = basic_bot_schema.partial().extend({
    user_id: z.number(),
    services: services_schema.optional(),
});

export const server_add_bot_schema = basic_bot_schema.extend({
    bot_type: z.number(),
    email: z.string(),
    is_active: z.boolean(),
    services: services_schema,
});
