import * as z from "zod/mini";

import {group_setting_value_schema} from "./types.ts";

export const StreamPostPolicy = {
    EVERYONE: 1,
    ADMINS: 2,
    RESTRICT_NEW_MEMBERS: 3,
    MODERATORS: 4,
} as const;
export type StreamPostPolicy = (typeof StreamPostPolicy)[keyof typeof StreamPostPolicy];

export const stream_permission_group_settings_schema = z.enum([
    "can_add_subscribers_group",
    "can_administer_channel_group",
    "can_create_topic_group",
    "can_delete_any_message_group",
    "can_delete_own_message_group",
    "can_move_messages_out_of_channel_group",
    "can_move_messages_within_channel_group",
    "can_remove_subscribers_group",
    "can_resolve_topics_group",
    "can_send_message_group",
    "can_subscribe_group",
]);
export type StreamPermissionGroupSetting = z.infer<typeof stream_permission_group_settings_schema>;

export const stream_topics_policy_schema = z.enum([
    "allow_empty_topic",
    "disable_empty_topic",
    "empty_topic_only",
    "inherit",
]);
export type StreamTopicsPolicy = z.infer<typeof stream_topics_policy_schema>;

// These types are taken from the `zerver/lib/types.py`.
export const stream_schema = z.object({
    can_add_subscribers_group: group_setting_value_schema,
    can_administer_channel_group: group_setting_value_schema,
    can_create_topic_group: group_setting_value_schema,
    can_delete_any_message_group: group_setting_value_schema,
    can_delete_own_message_group: group_setting_value_schema,
    can_move_messages_out_of_channel_group: group_setting_value_schema,
    can_move_messages_within_channel_group: group_setting_value_schema,
    can_remove_subscribers_group: group_setting_value_schema,
    can_resolve_topics_group: group_setting_value_schema,
    can_send_message_group: group_setting_value_schema,
    can_subscribe_group: group_setting_value_schema,
    creator_id: z.nullable(z.number()),
    date_created: z.number(),
    description: z.string(),
    first_message_id: z.nullable(z.number()),
    folder_id: z.nullable(z.number()),
    history_public_to_subscribers: z.boolean(),
    invite_only: z.boolean(),
    is_announcement_only: z.boolean(),
    is_archived: z.boolean(),
    is_recently_active: z.boolean(),
    is_web_public: z.boolean(),
    message_retention_days: z.nullable(z.number()),
    name: z.string(),
    rendered_description: z.string(),
    stream_id: z.number(),
    stream_post_policy: z.enum(StreamPostPolicy),
    topics_policy: stream_topics_policy_schema,
});

export const stream_specific_notification_settings_schema = z.object({
    audible_notifications: z.nullable(z.boolean()),
    desktop_notifications: z.nullable(z.boolean()),
    email_notifications: z.nullable(z.boolean()),
    push_notifications: z.nullable(z.boolean()),
    wildcard_mentions_notify: z.nullable(z.boolean()),
});

export const api_stream_schema = z.object({
    ...stream_schema.shape,
    stream_weekly_traffic: z.nullable(z.number()),
    // This field is stripped from subscriber objects when loading data
    // from the server. Always use `peer_data.get_subscriber_count` to
    // access channel subscriber counts, and see its comments for notes
    // about the possibility of inaccuracy in the presence of certain races.
    subscriber_count: z.number(),
});
export type APIStream = z.infer<typeof api_stream_schema>;

export const never_subscribed_stream_schema = z.object({
    ...api_stream_schema.shape,
    subscribers: z.optional(z.array(z.number())),
    partial_subscribers: z.optional(z.array(z.number())),
});

export const stream_properties_schema = z.object({
    ...stream_specific_notification_settings_schema.shape,
    color: z.string(),
    is_muted: z.boolean(),
    pin_to_top: z.boolean(),
});

// This is the raw data we get from the server for a subscription.
export const api_stream_subscription_schema = z.object({
    ...api_stream_schema.shape,
    ...stream_properties_schema.shape,
    subscribers: z.optional(z.array(z.number())),
    partial_subscribers: z.optional(z.array(z.number())),
});

export const updatable_stream_properties_schema = z.object({
    ...api_stream_subscription_schema.shape,
    in_home_view: z.boolean(),
});
export type UpdatableStreamProperties = z.infer<typeof updatable_stream_properties_schema>;
