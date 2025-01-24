import {z} from "zod";

import {attachment_schema} from "./attachments.ts";
import {server_add_bot_schema, server_update_bot_schema} from "./bot_types.ts";
import {presence_info_from_event_schema} from "./presence.ts";
import {realm_default_settings_schema} from "./realm_user_settings_defaults.ts";
import {server_message_schema} from "./server_message.ts";
import {export_consent_schema, realm_export_schema} from "./settings_exports.ts";
import {user_settings_property_schema} from "./settings_preferences.ts";
import {
    custom_profile_field_schema,
    muted_user_schema,
    onboarding_step_schema,
    raw_user_group_schema,
    realm_domain_schema,
    realm_emoji_map_schema,
    realm_linkifier_schema,
    realm_playground_schema,
    saved_snippet_schema,
    scheduled_message_schema,
    user_schema,
    user_topic_schema,
} from "./state_data.ts";
import {
    api_stream_schema,
    api_stream_subscription_schema,
    updatable_stream_properties_schema,
} from "./stream_types.ts";
import {anonymous_group_schema, group_setting_value_schema, topic_link_schema} from "./types.ts";
import {typing_event_schema} from "./typing_events.ts";
import {user_update_schema} from "./user_events.ts";
import {user_status_schema} from "./user_status_types.ts";

// These wrappers exist to work around Zod’s missing support for nested
// discriminatedUnion.
// https://github.com/colinhacks/zod/issues/1618
// https://github.com/colinhacks/zod/issues/1884
type EventOption<Key extends string> = z.ZodObject<
    Record<Key, z.ZodTypeAny> & {event: z.ZodType<Record<string, unknown>, z.ZodTypeDef, unknown>}
>;

function event_type<EventType extends string, Schema extends z.ZodTypeAny>(
    type: EventType,
    schema: Schema,
): z.ZodObject<{
    type: z.ZodLiteral<EventType>;
    event: z.ZodIntersection<z.ZodObject<{type: z.ZodLiteral<EventType>}>, Schema>;
}> {
    return z.object({type: z.literal(type), event: z.object({type: z.literal(type)}).and(schema)});
}

function event_op<EventOp extends string, Schema extends z.ZodTypeAny>(
    op: EventOp,
    schema: Schema,
): z.ZodObject<{
    op: z.ZodLiteral<EventOp>;
    event: z.ZodIntersection<z.ZodObject<{op: z.ZodLiteral<EventOp>}>, Schema>;
}> {
    return z.object({op: z.literal(op), event: z.object({op: z.literal(op)}).and(schema)});
}

function event_types<Types extends [EventOption<"type">, ...EventOption<"type">[]]>(
    options: Types,
): z.ZodType<
    z.output<Types[number]>["event"],
    z.ZodTypeDef,
    {type: string} & Record<string, unknown>
> {
    return z
        .object({type: z.string()})
        .catchall(z.unknown())
        .transform((event) => ({type: event.type, event}))
        .pipe(z.discriminatedUnion("type", options))
        .transform(({event}: z.output<Types[number]>) => event);
}

function event_ops<Types extends [EventOption<"op">, ...EventOption<"op">[]]>(
    options: Types,
): z.ZodType<
    z.output<Types[number]>["event"],
    z.ZodTypeDef,
    {op: string} & Record<string, unknown>
> {
    return z
        .object({op: z.string()})
        .catchall(z.unknown())
        .transform((event) => ({op: event.op, event}))
        .pipe(z.discriminatedUnion("op", options))
        .transform(({event}: z.output<Types[number]>) => event);
}

const stream_group_schema = z.object({
    name: z.string(),
    id: z.number(),
    description: z.string(),
    streams: z.array(z.number()),
});

const draft_schema = z.object({
    id: z.number(),
    type: z.enum(["", "stream", "private"]),
    to: z.array(z.number()),
    topic: z.string(),
    content: z.string(),
    timestamp: z.optional(z.number()),
});

const muted_topic_schema = z.tuple([z.string(), z.string(), z.number()]);

export const user_group_update_event_schema = z.object({
    id: z.number(),
    type: z.literal("user_group"),
    op: z.literal("update"),
    group_id: z.number(),
    data: z.object({
        name: z.optional(z.string()),
        description: z.optional(z.string()),
        can_add_members_group: z.optional(group_setting_value_schema),
        can_join_group: z.optional(group_setting_value_schema),
        can_leave_group: z.optional(group_setting_value_schema),
        can_manage_group: z.optional(group_setting_value_schema),
        can_mention_group: z.optional(group_setting_value_schema),
        can_remove_members_group: z.optional(group_setting_value_schema),
        deactivated: z.optional(z.boolean()),
    }),
});
export type UserGroupUpdateEvent = z.output<typeof user_group_update_event_schema>;

export const update_message_event_schema = z.object({
    id: z.number(),
    type: z.literal("update_message"),
    user_id: z.nullable(z.number()),
    rendering_only: z.boolean(),
    message_id: z.number(),
    message_ids: z.array(z.number()),
    flags: z.array(z.string()),
    edit_timestamp: z.number(),
    stream_name: z.optional(z.string()),
    stream_id: z.optional(z.number()),
    new_stream_id: z.optional(z.number()),
    propagate_mode: z.optional(z.string()),
    orig_subject: z.optional(z.string()),
    subject: z.optional(z.string()),
    topic_links: z.optional(z.array(topic_link_schema)),
    orig_content: z.optional(z.string()),
    orig_rendered_content: z.optional(z.string()),
    content: z.optional(z.string()),
    rendered_content: z.optional(z.string()),
    is_me_message: z.optional(z.boolean()),
    // The server is still using subject.
    // This will not be set until it gets fixed.
    topic: z.optional(z.string()),
});
export type UpdateMessageEvent = z.output<typeof update_message_event_schema>;

export const message_details_schema = z.record(
    z.coerce.number(),
    z.object({mentioned: z.optional(z.boolean())}).and(
        z.discriminatedUnion("type", [
            z.object({type: z.literal("private"), user_ids: z.array(z.number())}),
            z.object({
                type: z.literal("stream"),
                stream_id: z.number(),
                topic: z.string(),
                unmuted_stream_msg: z.boolean(),
            }),
        ]),
    ),
);
export type MessageDetails = z.output<typeof message_details_schema>;

export const base_server_event_schema = z
    .object({id: z.number(), type: z.string(), op: z.optional(z.string())})
    .catchall(z.unknown());

export type BaseServerEvent = z.output<typeof base_server_event_schema>;

export const server_event_schema = event_types([
    event_type("alert_words", z.object({alert_words: z.array(z.string())})),
    event_type(
        "attachment",
        z
            .discriminatedUnion("op", [
                z.object({op: z.literal("add"), attachment: attachment_schema}),
                z.object({op: z.literal("remove"), attachment: z.object({id: z.number()})}),
                z.object({op: z.literal("update"), attachment: attachment_schema}),
            ])
            .and(z.object({upload_space_used: z.number()})),
    ),
    event_type("custom_profile_fields", z.object({fields: z.array(custom_profile_field_schema)})),
    event_type(
        "default_stream_groups",
        z.object({default_stream_groups: z.array(stream_group_schema)}),
    ),
    event_type("default_streams", z.object({default_streams: z.array(z.number())})),
    event_type(
        "delete_message",
        z.discriminatedUnion("message_type", [
            z.object({message_type: z.literal("private"), message_ids: z.array(z.number())}),
            z.object({
                message_type: z.enum(["stream"]),
                message_ids: z.array(z.number()),
                stream_id: z.number(),
                topic: z.string(),
            }),
        ]),
    ),
    event_type(
        "drafts",
        z.discriminatedUnion("op", [
            z.object({op: z.literal("add"), drafts: z.array(draft_schema)}),
            z.object({op: z.literal("update"), draft: draft_schema}),
            z.object({op: z.literal("remove"), draft_id: z.number()}),
        ]),
    ),
    event_type(
        "saved_snippets",
        z.discriminatedUnion("op", [
            z.object({op: z.literal("add"), saved_snippet: saved_snippet_schema}),
            z.object({op: z.literal("remove"), saved_snippet_id: z.number()}),
        ]),
    ),
    event_type("has_zoom_token", z.object({value: z.boolean()})),
    event_type("heartbeat", z.object({})),
    event_type("onboarding_steps", z.object({onboarding_steps: z.array(onboarding_step_schema)})),
    event_type("invites_changed", z.object({})),
    event_type("muted_topics", z.object({muted_topics: z.array(muted_topic_schema)})),
    event_type("user_topic", user_topic_schema),
    event_type("muted_users", z.object({muted_users: z.array(muted_user_schema)})),
    event_type(
        "message",
        z.object({
            flags: z.array(z.string()),
            message: server_message_schema,
            local_message_id: z.optional(z.string()),
        }),
    ),
    event_type(
        "presence",
        z.object({
            user_id: z.number(),
            server_timestamp: z.number(),
            presence: presence_info_from_event_schema,
            email: z.optional(z.string()),
        }),
    ),
    event_type(
        "reaction",
        z.object({
            op: z.enum(["add", "remove"]),
            message_id: z.number(),
            emoji_name: z.string(),
            emoji_code: z.string(),
            reaction_type: z.enum(["unicode_emoji", "realm_emoji", "zulip_extra_emoji"]),
            user_id: z.number(),
        }),
    ),
    event_type(
        "realm",
        event_ops([
            event_op("deactivated", z.object({realm_id: z.number()})),
            event_op(
                "update",
                z.object({
                    property: z.string(),
                    value: z.union([z.boolean(), z.number(), z.string()]), // TODO/typescript: be specific depending on property
                }),
            ),
            event_op(
                "update_dict",
                z.discriminatedUnion("property", [
                    z.object({
                        property: z.literal("default"),
                        data: z.union([
                            z.object({allow_message_editing: z.boolean()}),
                            z.object({
                                authentication_methods: z.record(
                                    z.object({
                                        enabled: z.boolean(),
                                        available: z.boolean(),
                                        unavailable_reason: z.optional(z.string()),
                                    }),
                                ),
                            }),
                            z.object({allow_message_editing: z.boolean()}),
                            z.object({
                                message_content_edit_limit_seconds: z.optional(z.number()),
                            }),
                            z.record(
                                z.enum([
                                    "create_multiuse_invite_group",
                                    "can_access_all_users_group",
                                    "can_add_custom_emoji_group",
                                    "can_create_groups",
                                    "can_create_public_channel_group",
                                    "can_create_private_channel_group",
                                    "can_create_web_public_channel_group",
                                    "can_delete_any_message_group",
                                    "can_delete_own_message_group",
                                    "can_invite_users_group",
                                    "can_manage_all_groups",
                                    "can_move_messages_between_channels_group",
                                    "can_move_messages_between_topics_group",
                                    "direct_message_initiator_group",
                                    "direct_message_permission_group",
                                ]),
                                group_setting_value_schema,
                            ),
                            z.object({
                                plan_type: z.number(),
                                upload_quota_mib: z.optional(z.number()),
                                max_file_upload_size_mib: z.number(),
                            }),
                        ]),
                    }),
                    z.object({
                        property: z.literal("icon"),
                        data: z.object({icon_url: z.string(), icon_source: z.string()}),
                    }),
                    z.object({
                        property: z.literal("logo"),
                        data: z.object({logo_url: z.string(), logo_source: z.string()}),
                    }),
                    z.object({
                        property: z.literal("night_logo"),
                        data: z.object({night_logo_url: z.string(), night_logo_source: z.string()}),
                    }),
                ]),
            ),
        ]),
    ),
    event_type(
        "realm_bot",
        z.discriminatedUnion("op", [
            z.object({op: z.literal("add"), bot: server_add_bot_schema}),
            z.object({op: z.literal("delete"), bot: z.object({user_id: z.number()})}),
            z.object({op: z.literal("update"), bot: server_update_bot_schema}),
        ]),
    ),
    event_type(
        "realm_domains",
        z.discriminatedUnion("op", [
            z.object({op: z.literal("add"), realm_domain: realm_domain_schema}),
            z.object({op: z.literal("change"), realm_domain: realm_domain_schema}),
            z.object({op: z.literal("remove"), domain: z.string()}),
        ]),
    ),
    event_type(
        "realm_playgrounds",
        z.object({realm_playgrounds: z.array(realm_playground_schema)}),
    ),
    event_type(
        "realm_emoji",
        z.object({op: z.literal("update"), realm_emoji: realm_emoji_map_schema}),
    ),
    event_type("realm_export", z.object({exports: z.array(realm_export_schema)})),
    event_type("realm_export_consent", export_consent_schema),
    event_type("realm_linkifiers", z.object({realm_linkifiers: z.array(realm_linkifier_schema)})),
    event_type(
        "realm_user_settings_defaults",
        z.object({
            op: z.literal("update"),
            property: realm_default_settings_schema.keyof(),
            value: z.union([z.boolean(), z.number(), z.string()]), // TODO/typescript: be specific depending on property
        }),
    ),
    event_type(
        "realm_user",
        z.discriminatedUnion("op", [
            z.object({op: z.literal("add"), person: user_schema}),
            z.object({op: z.literal("update"), person: user_update_schema}),
            z.object({
                op: z.literal("remove"),
                person: z.object({user_id: z.number(), full_name: z.string()}),
            }),
        ]),
    ),
    event_type(
        "restart",
        z.object({
            zulip_version: z.string(),
            zulip_merge_base: z.string(),
            zulip_feature_level: z.number(),
            server_generation: z.number(),
        }),
    ),
    event_type("web_reload_client", z.object({immediate: z.boolean()})),
    event_type(
        "scheduled_messages",
        z.discriminatedUnion("op", [
            z.object({op: z.literal("add"), scheduled_messages: z.array(scheduled_message_schema)}),
            z.object({op: z.literal("update"), scheduled_message: scheduled_message_schema}),
            z.object({op: z.literal("remove"), scheduled_message_id: z.number()}),
        ]),
    ),
    event_type(
        "stream",
        event_ops([
            event_op("create", z.object({streams: z.array(api_stream_schema)})),
            event_op("delete", z.object({streams: z.array(api_stream_schema)})),
            event_op(
                "update",
                z.object({
                    property: updatable_stream_properties_schema.keyof(),
                    value: z.union([
                        z.boolean(),
                        z.number(),
                        z.string(),
                        anonymous_group_schema,
                        z.null(),
                    ]), // TODO/typescript: be specific depending on property
                    name: z.string(),
                    stream_id: z.number(),
                    rendered_description: z.optional(z.string()),
                    history_public_to_subscribers: z.optional(z.boolean()),
                    is_web_public: z.optional(z.boolean()),
                }),
            ),
        ]),
    ),
    event_type(
        "submessage",
        z.object({
            message_id: z.number(),
            submessage_id: z.number(),
            sender_id: z.number(),
            msg_type: z.string(),
            content: z.string(),
        }),
    ),
    event_type(
        "subscription",
        event_ops([
            event_op("add", z.object({subscriptions: z.array(api_stream_subscription_schema)})),
            event_op(
                "peer_add",
                z.object({user_ids: z.array(z.number()), stream_ids: z.array(z.number())}),
            ),
            event_op(
                "peer_remove",
                z.object({user_ids: z.array(z.number()), stream_ids: z.array(z.number())}),
            ),
            event_op(
                "remove",
                z.object({
                    subscriptions: z.array(z.object({name: z.string(), stream_id: z.number()})),
                }),
            ),
            event_op(
                "update",
                z.object({
                    property: updatable_stream_properties_schema.keyof(),
                    stream_id: z.number(),
                    value: z.union([z.boolean(), z.number(), z.string()]), // TODO/typescript: be specific depending on property
                }),
            ),
        ]),
    ),
    event_type("typing", typing_event_schema),
    // We do not receive type="update_display_settings" due to
    // user_settings_object capability
    event_type(
        "user_settings",
        z.object({
            op: z.literal("update"),
            property: user_settings_property_schema,
            value: z.union([z.boolean(), z.number(), z.string()]), // TODO/typescript: be specific depending on property
            language_name: z.optional(z.string()),
        }),
    ),
    // We do not receive type="update_global_notifications" due to
    // user_settings_object capability
    event_type("update_message", update_message_event_schema),
    event_type(
        "update_message_flags",
        z.discriminatedUnion("op", [
            z.object({
                op: z.literal("add"),
                operation: z.literal("add"),
                flag: z.string(),
                messages: z.array(z.number()),
                all: z.boolean(),
            }),
            z.object({
                op: z.literal("remove"),
                operation: z.literal("remove"),
                flag: z.string(),
                messages: z.array(z.number()),
                all: z.boolean(),
                message_details: message_details_schema,
            }),
        ]),
    ),
    event_type(
        "user_group",
        z.discriminatedUnion("op", [
            z.object({op: z.literal("add"), group: raw_user_group_schema}),
            z.object({
                op: z.literal("add_members"),
                group_id: z.number(),
                user_ids: z.array(z.number()),
            }),
            // We do not receive op="remove" due to include_deactivated_groups
            // capability
            z.object({
                op: z.literal("remove_members"),
                group_id: z.number(),
                user_ids: z.array(z.number()),
            }),
            user_group_update_event_schema,
            z.object({
                op: z.literal("add_subgroups"),
                group_id: z.number(),
                direct_subgroup_ids: z.array(z.number()),
            }),
            z.object({
                op: z.literal("remove_subgroups"),
                group_id: z.number(),
                direct_subgroup_ids: z.array(z.number()),
            }),
        ]),
    ),
    event_type("user_status", z.object({user_id: z.number()}).and(user_status_schema)),
]).and(z.object({id: z.number()}));

export type ServerEvent = z.output<typeof server_event_schema>;
