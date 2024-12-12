import {z} from "zod";

import {group_setting_value_schema} from "./types.ts";

export const enum StreamPostPolicy {
    EVERYONE = 1,
    ADMINS = 2,
    RESTRICT_NEW_MEMBERS = 3,
    MODERATORS = 4,
}

export const stream_permission_group_settings_schema = z.enum([
    "can_remove_subscribers_group",
    "can_administer_channel_group",
    "can_send_message_group",
]);
export type StreamPermissionGroupSetting = z.infer<typeof stream_permission_group_settings_schema>;

// These types are taken from the `zerver/lib/types.py`.
export const stream_schema = z.object({
    creator_id: z.number().nullable(),
    date_created: z.number(),
    description: z.string(),
    first_message_id: z.number().nullable(),
    history_public_to_subscribers: z.boolean(),
    invite_only: z.boolean(),
    is_announcement_only: z.boolean(),
    is_archived: z.boolean(),
    is_web_public: z.boolean(),
    message_retention_days: z.number().nullable(),
    name: z.string(),
    rendered_description: z.string(),
    stream_id: z.number(),
    stream_post_policy: z.nativeEnum({
        EVERYONE: StreamPostPolicy.EVERYONE,
        ADMINS: StreamPostPolicy.ADMINS,
        RESTRICT_NEW_MEMBERS: StreamPostPolicy.RESTRICT_NEW_MEMBERS,
        MODERATORS: StreamPostPolicy.MODERATORS,
    }),
    can_administer_channel_group: group_setting_value_schema,
    can_remove_subscribers_group: group_setting_value_schema,
    can_send_message_group: group_setting_value_schema,
    is_recently_active: z.boolean(),
});

export const stream_specific_notification_settings_schema = z.object({
    audible_notifications: z.boolean().nullable(),
    desktop_notifications: z.boolean().nullable(),
    email_notifications: z.boolean().nullable(),
    push_notifications: z.boolean().nullable(),
    wildcard_mentions_notify: z.boolean().nullable(),
});

export const api_stream_schema = stream_schema.extend({
    stream_weekly_traffic: z.number().nullable(),
});

export const never_subscribed_stream_schema = api_stream_schema.extend({
    subscribers: z.array(z.number()).optional(),
});

export const stream_properties_schema = stream_specific_notification_settings_schema.extend({
    color: z.string(),
    is_muted: z.boolean(),
    pin_to_top: z.boolean(),
});

// This is the raw data we get from the server for a subscription.
export const api_stream_subscription_schema = api_stream_schema
    .merge(stream_properties_schema)
    .extend({
        subscribers: z.array(z.number()).optional(),
    });

export const updatable_stream_properties_schema = api_stream_subscription_schema.extend({
    in_home_view: z.boolean(),
});
export type UpdatableStreamProperties = z.infer<typeof updatable_stream_properties_schema>;
