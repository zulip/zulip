import * as v from "valibot";

import type {StateData} from "./state_data.ts";

export const stream_notification_settings_schema = v.object({
    enable_stream_audible_notifications: v.boolean(),
    enable_stream_desktop_notifications: v.boolean(),
    enable_stream_email_notifications: v.boolean(),
    enable_stream_push_notifications: v.boolean(),
    wildcard_mentions_notify: v.boolean(),
});
export type StreamNotificationSettings = v.InferOutput<typeof stream_notification_settings_schema>;

export const pm_notification_settings_schema = v.object({
    enable_desktop_notifications: v.boolean(),
    enable_offline_email_notifications: v.boolean(),
    enable_offline_push_notifications: v.boolean(),
    enable_sounds: v.boolean(),
});
export type PmNotificationSettings = v.InferOutput<typeof pm_notification_settings_schema>;

export const followed_topic_notification_settings_schema = v.object({
    enable_followed_topic_audible_notifications: v.boolean(),
    enable_followed_topic_desktop_notifications: v.boolean(),
    enable_followed_topic_email_notifications: v.boolean(),
    enable_followed_topic_push_notifications: v.boolean(),
    enable_followed_topic_wildcard_mentions_notify: v.boolean(),
});
export type FollowedTopicNotificationSettings = v.InferOutput<
    typeof followed_topic_notification_settings_schema
>;

export const user_settings_schema = v.object({
    ...stream_notification_settings_schema.entries,
    ...pm_notification_settings_schema.entries,
    ...followed_topic_notification_settings_schema.entries,
    allow_private_data_export: v.boolean(),
    automatically_follow_topics_policy: v.number(),
    automatically_follow_topics_where_mentioned: v.boolean(),
    automatically_unmute_topics_in_muted_streams_policy: v.number(),
    available_notification_sounds: v.array(v.string()),
    color_scheme: v.number(),
    default_language: v.string(),
    demote_inactive_streams: v.number(),
    dense_mode: v.boolean(),
    desktop_icon_count_display: v.number(),
    display_emoji_reaction_users: v.boolean(),
    email_address_visibility: v.number(),
    email_notifications_batching_period_seconds: v.number(),
    emojiset: v.string(),
    emojiset_choices: v.array(v.object({key: v.string(), text: v.string()})),
    enable_digest_emails: v.boolean(),
    enable_drafts_synchronization: v.boolean(),
    enable_login_emails: v.boolean(),
    enable_marketing_emails: v.boolean(),
    enable_online_push_notifications: v.boolean(),
    enter_sends: v.boolean(),
    fluid_layout_width: v.boolean(),
    high_contrast_mode: v.boolean(),
    left_side_userlist: v.boolean(),
    message_content_in_email_notifications: v.boolean(),
    notification_sound: v.string(),
    pm_content_in_desktop_notifications: v.boolean(),
    presence_enabled: v.boolean(),
    realm_name_in_email_notifications_policy: v.number(),
    receives_typing_notifications: v.boolean(),
    send_private_typing_notifications: v.boolean(),
    send_read_receipts: v.boolean(),
    send_stream_typing_notifications: v.boolean(),
    starred_message_counts: v.boolean(),
    timezone: v.string(),
    translate_emoticons: v.boolean(),
    twenty_four_hour_time: v.boolean(),
    user_list_style: v.number(),
    web_animate_image_previews: v.picklist(["always", "on_hover", "never"]),
    web_channel_default_view: v.number(),
    web_escape_navigates_to_home_view: v.boolean(),
    web_font_size_px: v.number(),
    web_home_view: v.picklist(["inbox", "recent_topics", "all_messages"]),
    web_line_height_percent: v.number(),
    web_mark_read_on_scroll_policy: v.number(),
    web_navigate_to_sent_message: v.boolean(),
    web_stream_unreads_count_display_policy: v.number(),
    web_suggest_update_timezone: v.boolean(),
});
export type UserSettings = v.InferOutput<typeof user_settings_schema>;

export let user_settings: UserSettings;

export function initialize_user_settings(params: StateData["user_settings"]): void {
    user_settings = params.user_settings;
}
