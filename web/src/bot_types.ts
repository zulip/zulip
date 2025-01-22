import * as v from "valibot";

const basic_bot_schema = v.object({
    api_key: v.string(),
    avatar_url: v.string(),
    bot_type: v.number(),
    default_all_public_streams: v.boolean(),
    default_events_register_stream: v.nullable(v.string()),
    default_sending_stream: v.nullable(v.string()),
    email: v.string(),
    full_name: v.string(),
    is_active: v.boolean(),
    owner_id: v.nullable(v.number()),
    user_id: v.number(),
});

const outgoing_service_schema = v.object({
    base_url: v.string(),
    interface: v.number(),
    token: v.string(),
});

const embedded_service_schema = v.object({
    config_data: v.record(v.string(), v.string()),
    service_name: v.string(),
});

export const services_schema = v.union([
    v.array(outgoing_service_schema),
    v.array(embedded_service_schema),
]);

export const server_update_bot_schema = v.object({
    ...v.partial(basic_bot_schema).entries,
    user_id: v.number(),
    services: v.optional(services_schema),
});

export const server_add_bot_schema = v.object({
    ...basic_bot_schema.entries,
    bot_type: v.number(),
    email: v.string(),
    is_active: v.boolean(),
    services: services_schema,
});
