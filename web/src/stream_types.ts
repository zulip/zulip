import * as v from "valibot";

import {group_setting_value_schema} from "./types.ts";

export const enum StreamPostPolicy {
    EVERYONE = 1,
    ADMINS = 2,
    RESTRICT_NEW_MEMBERS = 3,
    MODERATORS = 4,
}

export const stream_permission_group_settings_schema = v.picklist([
    "can_remove_subscribers_group",
    "can_administer_channel_group",
]);
export type StreamPermissionGroupSetting = v.InferOutput<
    typeof stream_permission_group_settings_schema
>;

// These types are taken from the `zerver/lib/types.py`.
export const stream_schema = v.object({
    creator_id: v.nullable(v.number()),
    date_created: v.number(),
    description: v.string(),
    first_message_id: v.nullable(v.number()),
    history_public_to_subscribers: v.boolean(),
    invite_only: v.boolean(),
    is_announcement_only: v.boolean(),
    is_archived: v.boolean(),
    is_web_public: v.boolean(),
    message_retention_days: v.nullable(v.number()),
    name: v.string(),
    rendered_description: v.string(),
    stream_id: v.number(),
    stream_post_policy: v.enum({
        EVERYONE: StreamPostPolicy.EVERYONE,
        ADMINS: StreamPostPolicy.ADMINS,
        RESTRICT_NEW_MEMBERS: StreamPostPolicy.RESTRICT_NEW_MEMBERS,
        MODERATORS: StreamPostPolicy.MODERATORS,
    }),
    can_administer_channel_group: group_setting_value_schema,
    can_remove_subscribers_group: group_setting_value_schema,
    is_recently_active: v.boolean(),
});

export const stream_specific_notification_settings_schema = v.object({
    audible_notifications: v.nullable(v.boolean()),
    desktop_notifications: v.nullable(v.boolean()),
    email_notifications: v.nullable(v.boolean()),
    push_notifications: v.nullable(v.boolean()),
    wildcard_mentions_notify: v.nullable(v.boolean()),
});

export const never_subscribed_stream_schema = v.object({
    ...stream_schema.entries,
    stream_weekly_traffic: v.nullable(v.number()),
    subscribers: v.optional(v.array(v.number())),
});

export const stream_properties_schema = v.object({
    ...stream_specific_notification_settings_schema.entries,
    color: v.string(),
    is_muted: v.boolean(),
    pin_to_top: v.boolean(),
});

// This is the raw data we get from the server for a subscription.
export const api_stream_subscription_schema = v.object({
    ...stream_schema.entries,
    ...stream_properties_schema.entries,
    email_address: v.optional(v.string()),
    stream_weekly_traffic: v.nullable(v.number()),
    subscribers: v.optional(v.array(v.number())),
});
