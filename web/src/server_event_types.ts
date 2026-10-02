import * as z from "zod/mini";

import {group_setting_value_schema, topic_link_schema} from "./types.ts";

// Event types the web app passes to /register as fetch_event_types.
//
// The server uses this list for two things: which pieces of the initial
// state to compute, and which of the events that arrive while it computes
// them get applied to the result. An event type missing here is dropped
// rather than delivered later, so the list needs both the names of the
// state pieces we want (e.g. "realm_user_groups") and the names of the
// events that update them (e.g. "user_group").
//
// "stream" is omitted deliberately: the web app works from "subscription"
// data instead, and requesting it would make the server compute metadata
// for every channel in the organization.
// Keep in sync with want() and apply_event() in zerver/lib/events.py.
export const FETCH_EVENT_TYPES: string[] = [
    "alert_words",
    "channel_folder",
    "channel_folders",
    "custom_profile_fields",
    "default_stream_groups",
    "default_streams",
    "delete_message",
    "device",
    "drafts",
    "giphy",
    "has_webex_token",
    "has_zoom_token",
    "klipy",
    "message",
    "muted_users",
    "navigation_view",
    "navigation_views",
    "onboarding_steps",
    "presence",
    "realm",
    "realm_billing",
    "realm_bot",
    "realm_domains",
    "realm_embedded_bots",
    "realm_emoji",
    "realm_filters",
    "realm_incoming_webhook_bots",
    "realm_linkifiers",
    "realm_playgrounds",
    "realm_user",
    "realm_user_groups",
    "realm_user_settings_defaults",
    "recent_private_conversations",
    "reminders",
    "saved_snippets",
    "scheduled_messages",
    "starred_messages",
    "stop_words",
    "subscription",
    "tenor",
    "update_message",
    "update_message_flags",
    "user_group",
    "user_settings",
    "user_status",
    "user_topic",
    "video_calls",
];

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
    z.coerce.number<string>(),
    z.intersection(
        z.object({mentioned: z.optional(z.boolean())}),
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

export const channel_folder_update_event_schema = z.object({
    id: z.number(),
    type: z.literal("channel_folder"),
    op: z.literal("update"),
    channel_folder_id: z.number(),
    data: z.object({
        name: z.optional(z.string()),
        description: z.optional(z.string()),
        rendered_description: z.optional(z.string()),
        is_archived: z.optional(z.boolean()),
    }),
});
export type ChannelFolderUpdateEvent = z.output<typeof channel_folder_update_event_schema>;
