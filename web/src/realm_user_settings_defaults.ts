import {z} from "zod";

import type {StateData} from "./state_data";

export const realm_default_settings_schema = z.object({
    automatically_follow_topics_policy: z.number(),
    automatically_follow_topics_where_mentioned: z.boolean(),
    automatically_unmute_topics_in_muted_streams_policy: z.number(),
    color_scheme: z.number(),
    default_language: z.string(),
    demote_inactive_streams: z.number(),
    dense_mode: z.boolean(),
    desktop_icon_count_display: z.number(),
    display_emoji_reaction_users: z.boolean(),
    email_notifications_batching_period_seconds: z.number(),
    emojiset: z.string(),
    enable_desktop_notifications: z.boolean(),
    enable_digest_emails: z.boolean(),
    enable_drafts_synchronization: z.boolean(),
    enable_followed_topic_audible_notifications: z.boolean(),
    enable_followed_topic_desktop_notifications: z.boolean(),
    enable_followed_topic_email_notifications: z.boolean(),
    enable_followed_topic_push_notifications: z.boolean(),
    enable_followed_topic_wildcard_mentions_notify: z.boolean(),
    enable_login_emails: z.boolean(),
    enable_marketing_emails: z.boolean(),
    enable_offline_email_notifications: z.boolean(),
    enable_offline_push_notifications: z.boolean(),
    enable_online_push_notifications: z.boolean(),
    enable_sounds: z.boolean(),
    enable_stream_audible_notifications: z.boolean(),
    enable_stream_desktop_notifications: z.boolean(),
    enable_stream_email_notifications: z.boolean(),
    enable_stream_push_notifications: z.boolean(),
    enter_sends: z.boolean(),
    fluid_layout_width: z.boolean(),
    high_contrast_mode: z.boolean(),
    message_content_in_email_notifications: z.boolean(),
    notification_sound: z.string(),
    pm_content_in_desktop_notifications: z.boolean(),
    presence_enabled: z.boolean(),
    realm_name_in_email_notifications_policy: z.number(),
    receives_typing_notifications: z.boolean(),
    send_private_typing_notifications: z.boolean(),
    send_stream_typing_notifications: z.boolean(),
    starred_message_counts: z.boolean(),
    translate_emoticons: z.boolean(),
    twenty_four_hour_time: z.boolean(),
    custom_default_days: z.number(),
    custom_default_hours: z.number(),
    user_list_style: z.number(),
    web_escape_navigates_to_home_view: z.boolean(),
    web_font_size_px: z.number(),
    web_home_view: z.string(),
    web_line_height_percent: z.number(),
    web_mark_read_on_scroll_policy: z.number(),
    web_stream_unreads_count_display_policy: z.number(),
    wildcard_mentions_notify: z.boolean(),
});
export type RealmDefaultSettings = z.infer<typeof realm_default_settings_schema>;

export let realm_user_settings_defaults: RealmDefaultSettings;

export function initialize(params: StateData["realm_settings_defaults"]): void {
    realm_user_settings_defaults = params.realm_user_settings_defaults;
}
