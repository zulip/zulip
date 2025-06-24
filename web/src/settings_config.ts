import Handlebars from "handlebars/runtime.js";

import {page_params} from "./base_page_params.ts";
import type {
    GroupGroupSettingName,
    RealmGroupSettingName,
    StreamGroupSettingName,
} from "./group_permission_settings.ts";
import {$t, $t_html} from "./i18n.ts";
import type {RealmDefaultSettings} from "./realm_user_settings_defaults.ts";
import {realm} from "./state_data.ts";
import type {StreamSpecificNotificationSettings} from "./sub_store.ts";
import type {
    FollowedTopicNotificationSettings,
    PmNotificationSettings,
    StreamNotificationSettings,
    UserSettings,
} from "./user_settings.ts";
import * as util from "./util.ts";

/*
    This file contains translations between the integer values used in
    the Zulip API to describe values in dropdowns, radio buttons, and
    similar widgets and the user-facing strings that should be used to
    describe them, as well as data details like sort orders that may
    be useful for some widgets.

    We plan to eventually transition much of this file to have a more
    standard format and then to be populated using data sent from the
    Zulip server in `page_params`, so that the data is available for
    other parts of the ecosystem to use (including the mobile apps and
    API documentation) without a ton of copying.
*/

export const demote_inactive_streams_values = {
    automatic: {
        code: 1,
        description: $t({defaultMessage: "Automatic"}),
    },
    always: {
        code: 2,
        description: $t({defaultMessage: "Always"}),
    },
    never: {
        code: 3,
        description: $t({defaultMessage: "Never"}),
    },
};

export const web_mark_read_on_scroll_policy_values = {
    always: {
        code: 1,
        description: $t({defaultMessage: "Always"}),
    },
    conversation_only: {
        code: 2,
        description: $t({defaultMessage: "Only in conversation views"}),
    },
    never: {
        code: 3,
        description: $t({defaultMessage: "Never"}),
    },
};

export const web_channel_default_view_values = {
    top_topic_in_channel: {
        code: 1,
        description: $t({defaultMessage: "Top topic in the channel"}),
    },
    list_of_topics: {
        code: 3,
        description: $t({defaultMessage: "List of topics"}),
    },
    channel_feed: {
        code: 2,
        description: $t({defaultMessage: "Channel feed"}),
    },
};

export const user_list_style_values: {
    compact: {
        code: number;
        description: string;
    };
    with_status: {
        code: number;
        description: string;
    };
    with_avatar: {
        code: number;
        description: string;
    };
} = {
    compact: {
        code: 1,
        description: $t({defaultMessage: "Compact"}),
    },
    with_status: {
        code: 2,
        description: $t({defaultMessage: "Show status text"}),
    },
    with_avatar: {
        code: 3,
        description: $t({defaultMessage: "Show avatar"}),
    },
};

export const web_animate_image_previews_values = {
    always: {
        code: "always",
        description: $t({defaultMessage: "Always"}),
    },
    on_hover: {
        code: "on_hover",
        description: $t({defaultMessage: "On hover"}),
    },
    never: {
        code: "never",
        description: $t({defaultMessage: "Only in image viewer"}),
    },
};

export const resolved_topic_notice_auto_read_policy_values = {
    always: {
        code: "always",
        description: $t({defaultMessage: "Always"}),
    },
    except_followed: {
        code: "except_followed",
        description: $t({defaultMessage: "Except in topics I'm following"}),
    },
    never: {
        code: "never",
        description: $t({defaultMessage: "Never"}),
    },
};

export const web_stream_unreads_count_display_policy_values = {
    all_streams: {
        code: 1,
        description: $t({defaultMessage: "All channels"}),
    },
    unmuted_streams: {
        code: 2,
        description: $t({defaultMessage: "Unmuted channels and topics"}),
    },
    no_streams: {
        code: 3,
        description: $t({defaultMessage: "No channels"}),
    },
};

export const web_home_view_values = {
    inbox: {
        code: "inbox",
        description: $t({defaultMessage: "Inbox"}),
    },
    recent_topics: {
        code: "recent_topics",
        description: $t({defaultMessage: "Recent conversations"}),
    },
    all_messages: {
        code: "all_messages",
        description: $t({defaultMessage: "Combined feed"}),
    },
};

type ColorScheme = "automatic" | "dark" | "light";
export type ColorSchemeValues = Record<
    ColorScheme,
    {
        code: number;
        description: string;
    }
>;

export const color_scheme_values = {
    automatic: {
        code: 1,
        description: $t({defaultMessage: "Automatic (follows system settings)"}),
    },
    light: {
        code: 3,
        description: $t({defaultMessage: "Light"}),
    },
    dark: {
        code: 2,
        description: $t({defaultMessage: "Dark"}),
    },
};

export const twenty_four_hour_time_values = {
    twenty_four_hour_clock: {
        value: true,
        description: $t({defaultMessage: "24-hour clock (17:00)"}),
    },
    twelve_hour_clock: {
        value: false,
        description: $t({defaultMessage: "12-hour clock (5:00 PM)"}),
    },
};

export type DisplaySettings = {
    settings: {
        user_preferences: string[];
    };
    render_group?: boolean;
};

/* istanbul ignore next */
export const get_information_density_preferences = (): DisplaySettings => ({
    render_group: page_params.development_environment,
    settings: {
        user_preferences: ["web_font_size_px", "web_line_height_percent"],
    },
});

type SettingsRenderOnly = {
    hide_ai_features: boolean;
    high_contrast_mode: boolean;
    web_font_size_px: boolean;
    web_line_height_percent: boolean;
};

/* istanbul ignore next */
export const get_settings_render_only = (): SettingsRenderOnly => ({
    // Offer the UI for hiding AI features exactly when the server
    // supports doing so.
    hide_ai_features: realm.server_can_summarize_topics,
    high_contrast_mode: page_params.development_environment,
    web_font_size_px: page_params.development_environment,
    web_line_height_percent: page_params.development_environment,
});

export const email_address_visibility_values = {
    everyone: {
        code: 1,
        description: $t({defaultMessage: "Admins, moderators, members and guests"}),
    },
    members: {
        code: 2,
        description: $t({defaultMessage: "Admins, moderators and members"}),
    },
    moderators: {
        code: 5,
        description: $t({defaultMessage: "Admins and moderators"}),
    },
    admins_only: {
        code: 3,
        description: $t({defaultMessage: "Admins only"}),
    },
    nobody: {
        code: 4,
        description: $t({defaultMessage: "Nobody"}),
    },
};

export const common_policy_values = {
    by_admins_only: {
        order: 1,
        code: 2,
        description: $t({defaultMessage: "Admins"}),
    },
    by_moderators_only: {
        order: 2,
        code: 4,
        description: $t({defaultMessage: "Admins and moderators"}),
    },
    by_full_members: {
        order: 3,
        code: 3,
        description: $t({defaultMessage: "Admins, moderators and full members"}),
    },
    by_members: {
        order: 4,
        code: 1,
        description: $t({defaultMessage: "Admins, moderators and members"}),
    },
};

export const message_edit_history_visibility_policy_values = {
    always: {
        code: "all",
        description: $t({defaultMessage: "Show edits and moves"}),
    },
    moves_only: {
        code: "moves",
        description: $t({defaultMessage: "Move history only"}),
    },
    never: {
        code: "none",
        description: $t({defaultMessage: "Don't allow"}),
    },
};

type PolicyValue = {
    code: string;
    description: string;
};

type RealmTopicsPolicyValues = {
    allow_empty_topic: PolicyValue;
    disable_empty_topic: PolicyValue;
};

type StreamTopicsPolicyValues = {
    inherit: PolicyValue;
} & RealmTopicsPolicyValues;

export const get_realm_topics_policy_values = (): RealmTopicsPolicyValues => {
    const empty_topic_name = util.get_final_topic_display_name("");

    return {
        allow_empty_topic: {
            code: "allow_empty_topic",
            description: $t(
                {defaultMessage: '"{empty_topic_name}" topic allowed'},
                {empty_topic_name},
            ),
        },
        disable_empty_topic: {
            code: "disable_empty_topic",
            description: $t({defaultMessage: 'No "{empty_topic_name}" topic'}, {empty_topic_name}),
        },
    };
};

export const get_stream_topics_policy_values = (): StreamTopicsPolicyValues => {
    const realm_topics_policy_values = get_realm_topics_policy_values();

    return {
        inherit: {
            code: "inherit",
            description: $t({defaultMessage: "Automatic"}),
        },
        ...realm_topics_policy_values,
    };
};

export const time_limit_dropdown_values = [
    {
        text: $t({defaultMessage: "Any time"}),
        value: "any_time",
    },
    {
        text: $t(
            {defaultMessage: "Up to {time_limit} after posting"},
            {time_limit: $t({defaultMessage: "2 minutes"})},
        ),
        value: 2 * 60,
    },
    {
        text: $t(
            {defaultMessage: "Up to {time_limit} after posting"},
            {time_limit: $t({defaultMessage: "10 minutes"})},
        ),
        value: 10 * 60,
    },
    {
        text: $t(
            {defaultMessage: "Up to {time_limit} after posting"},
            {time_limit: $t({defaultMessage: "1 hour"})},
        ),
        value: 60 * 60,
    },
    {
        text: $t(
            {defaultMessage: "Up to {time_limit} after posting"},
            {time_limit: $t({defaultMessage: "1 day"})},
        ),
        value: 24 * 60 * 60,
    },
    {
        text: $t(
            {defaultMessage: "Up to {time_limit} after posting"},
            {time_limit: $t({defaultMessage: "1 week"})},
        ),
        value: 7 * 24 * 60 * 60,
    },
    {
        text: $t({defaultMessage: "Custom"}),
        value: "custom_period",
    },
];
export const msg_edit_limit_dropdown_values = time_limit_dropdown_values;
export const msg_delete_limit_dropdown_values = time_limit_dropdown_values;
export const msg_move_limit_dropdown_values = time_limit_dropdown_values;

export const waiting_period_threshold_dropdown_values = [
    {
        description: $t({defaultMessage: "None"}),
        code: 0,
    },
    {
        description: $t({defaultMessage: "3 days"}),
        code: 3,
    },
    {
        description: $t({defaultMessage: "Custom"}),
        code: "custom_period",
    },
];

export const retain_message_forever = -1;

export const user_role_values = {
    guest: {
        code: 600,
        description: $t({defaultMessage: "Guest"}),
    },
    member: {
        code: 400,
        description: $t({defaultMessage: "Member"}),
    },
    moderator: {
        code: 300,
        description: $t({defaultMessage: "Moderator"}),
    },
    admin: {
        code: 200,
        description: $t({defaultMessage: "Administrator"}),
    },
    owner: {
        code: 100,
        description: $t({defaultMessage: "Owner"}),
    },
};

export const all_org_type_values = {
    // When org_type was added to the database model, 'unspecified'
    // was the default for existing organizations. To discourage
    // organizations keeping (or selecting) it as an option, we
    // use an empty string for its description.
    unspecified: {
        code: 0,
        description: "",
    },
    business: {
        code: 10,
        description: $t({defaultMessage: "Business"}),
    },
    opensource: {
        code: 20,
        description: $t({defaultMessage: "Open-source project"}),
    },
    education_nonprofit: {
        code: 30,
        description: $t({defaultMessage: "Education (non-profit)"}),
    },
    education: {
        code: 35,
        description: $t({defaultMessage: "Education (for-profit)"}),
    },
    research: {
        code: 40,
        description: $t({defaultMessage: "Research"}),
    },
    event: {
        code: 50,
        description: $t({defaultMessage: "Event or conference"}),
    },
    nonprofit: {
        code: 60,
        description: $t({defaultMessage: "Non-profit (registered)"}),
    },
    government: {
        code: 70,
        description: $t({defaultMessage: "Government"}),
    },
    political_group: {
        code: 80,
        description: $t({defaultMessage: "Political group"}),
    },
    community: {
        code: 90,
        description: $t({defaultMessage: "Community"}),
    },
    personal: {
        code: 100,
        description: $t({defaultMessage: "Personal"}),
    },
    other: {
        code: 1000,
        description: $t({defaultMessage: "Other"}),
    },
};

// Remove the 'unspecified' org_type for dropdown menu options
// when an org_type other than 'unspecified' has been selected.
export const defined_org_type_values = Object.fromEntries(
    Object.entries(all_org_type_values).slice(1),
);

export const expires_in_values = {
    // Backend support for this configuration is not available yet.
    // hour: {
    //     value: 1,
    //     description: $t({defaultMessage: "1 hour"}),
    //     default: false,
    // },
    day: {
        value: 24 * 60,
        description: $t({defaultMessage: "1 day"}),
        default: false,
    },
    three_days: {
        value: 3 * 24 * 60,
        description: $t({defaultMessage: "3 days"}),
        default: false,
    },
    ten_days: {
        value: 10 * 24 * 60,
        description: $t({defaultMessage: "10 days"}),
        default: true,
    },
    thirty_days: {
        value: 30 * 24 * 60,
        description: $t({defaultMessage: "30 days"}),
        default: false,
    },
    never: {
        // Ideally we'd just store `null`, not the string `"null"`, but
        // .val() will read null back as `""`.  Custom logic in
        // get_common_invitation_data converts this back to `null`
        // before sending to the server.
        value: "null",
        description: $t({defaultMessage: "Never expires"}),
        default: false,
    },
    custom: {
        value: "custom",
        description: $t({defaultMessage: "Custom"}),
        default: false,
    },
};

export const custom_time_unit_values = {
    minutes: {
        name: "minutes",
        description: $t({defaultMessage: "minutes"}),
    },
    hours: {
        name: "hours",
        description: $t({defaultMessage: "hours"}),
    },
    days: {
        name: "days",
        description: $t({defaultMessage: "days"}),
    },
    weeks: {
        name: "weeks",
        description: $t({defaultMessage: "weeks"}),
    },
};

export const realm_deletion_in_values = {
    immediately: {
        value: 0,
        description: $t({defaultMessage: "Immediately"}),
        default: false,
    },
    fourteen_days: {
        value: 14 * 24 * 60,
        description: $t({defaultMessage: "14 days"}),
        default: true,
    },
    thirty_days: {
        value: 30 * 24 * 60,
        description: $t({defaultMessage: "30 days"}),
        default: false,
    },
    ninety_days: {
        value: 90 * 24 * 60,
        description: $t({defaultMessage: "90 days"}),
        default: false,
    },
    one_year: {
        value: 365 * 24 * 60,
        description: $t({defaultMessage: "1 year"}),
        default: false,
    },
    two_years: {
        value: 365 * 24 * 60 * 2,
        description: $t({defaultMessage: "2 years"}),
        default: false,
    },
    never: {
        // Ideally we'd just store `null`, not the string `"null"`, but
        // .val() will read null back as `""`.  Custom logic in
        // do_deactivate_realm converts this back to `null`
        // before sending to the server.
        value: "null",
        description: $t({defaultMessage: "Never"}),
        default: false,
    },
    custom: {
        value: "custom",
        description: $t({defaultMessage: "Custom"}),
        default: false,
    },
};

const user_role_array = Object.values(user_role_values);
export const user_role_map = new Map(user_role_array.map((role) => [role.code, role.description]));

export const preferences_settings_labels = {
    default_language_settings_label: $t({defaultMessage: "Language"}),
    display_emoji_reaction_users: new Handlebars.SafeString(
        $t_html({
            defaultMessage:
                "Display names of reacting users when few users have reacted to a message",
        }),
    ),
    fluid_layout_width: $t({defaultMessage: "Use full width on wide screens"}),
    hide_ai_features: $t({defaultMessage: "Hide AI features"}),
    high_contrast_mode: $t({defaultMessage: "High contrast mode"}),
    enter_sends: new Handlebars.SafeString(
        $t_html({defaultMessage: "<kbd>Enter</kbd> sends when composing a message"}),
    ),
    receives_typing_notifications: $t({defaultMessage: "Show when other users are typing"}),
    starred_message_counts: $t({defaultMessage: "Show counts for starred messages"}),
    twenty_four_hour_time: $t({defaultMessage: "Time format"}),
    translate_emoticons: new Handlebars.SafeString(
        $t_html({
            defaultMessage: "Convert emoticons before sending (<code>:)</code> becomes 🙂)",
        }),
    ),
    web_suggest_update_timezone: $t({
        defaultMessage: "Offer to update to my computer's time zone",
    }),
    web_escape_navigates_to_home_view: $t({defaultMessage: "Escape key navigates to home view"}),
    web_font_size_px: $t({defaultMessage: "Message-area font size (px)"}),
    web_line_height_percent: $t({defaultMessage: "Message-area line height (%)"}),
    web_navigate_to_sent_message: $t({
        defaultMessage: "Automatically go to conversation where you sent a message",
    }),
};

export const notification_settings_labels = {
    automatically_follow_topics_policy: $t({
        defaultMessage: "Automatically follow topics based on my participation",
    }),
    automatically_follow_topics_where_mentioned: $t({
        defaultMessage: "Automatically follow topics where I'm mentioned",
    }),
    automatically_unmute_topics_in_muted_streams_policy: $t({
        defaultMessage: "Automatically unmute topics in muted channels",
    }),
    desktop_icon_count_display: $t({
        defaultMessage: "Unread count badge (appears in desktop sidebar and browser tab)",
    }),
    enable_online_push_notifications: $t({
        defaultMessage: "Send mobile notifications even if I'm online",
    }),
    enable_digest_emails: $t({defaultMessage: "Send digest emails when I'm away"}),
    enable_login_emails: $t({
        defaultMessage: "Send email notifications for new logins to my account",
    }),
    enable_marketing_emails: $t({
        defaultMessage: "Send me Zulip's low-traffic newsletter (a few emails a year)",
    }),
    message_content_in_email_notifications: $t({
        defaultMessage: "Include message content in message notification emails",
    }),
    pm_content_in_desktop_notifications: $t({
        defaultMessage: "Include content of direct messages in desktop notifications",
    }),
    realm_name_in_email_notifications_policy: $t({
        defaultMessage: "Include organization name in subject of message notification emails",
    }),
};

export const realm_user_settings_defaults_labels = {
    ...notification_settings_labels,
    ...preferences_settings_labels,

    /* Overrides to remove "I" from labels for the realm-level versions of these labels. */
    enable_online_push_notifications: $t({
        defaultMessage: "Send mobile notifications even if user is online",
    }),
    enable_digest_emails: $t({defaultMessage: "Send digest emails when user is away"}),

    presence_enabled: $t({
        defaultMessage: "Display availability to other users",
    }),
    presence_enabled_parens_text: $t({defaultMessage: "invisible mode off"}),
    send_read_receipts: $t({defaultMessage: "Allow other users to view read receipts"}),
    send_private_typing_notifications: $t({
        defaultMessage: "Let recipients see when a user is typing direct messages",
    }),
    send_stream_typing_notifications: $t({
        defaultMessage: "Let recipients see when a user is typing channel messages",
    }),
};

export const all_group_setting_labels = {
    realm: {
        create_multiuse_invite_group: $t({
            defaultMessage: "Who can create reusable invitation links",
        }),
        can_invite_users_group: $t({defaultMessage: "Who can send email invitations to new users"}),
        can_create_public_channel_group: $t({defaultMessage: "Who can create public channels"}),
        can_create_web_public_channel_group: $t({
            defaultMessage: "Who can create web-public channels",
        }),
        can_create_private_channel_group: $t({defaultMessage: "Who can create private channels"}),
        can_add_subscribers_group: $t({defaultMessage: "Who can subscribe others to channels"}),
        direct_message_permission_group: $t({
            defaultMessage: "Who can authorize a direct message conversation",
        }),
        direct_message_initiator_group: $t({
            defaultMessage: "Who can start a direct message conversation",
        }),
        can_manage_all_groups: $t({defaultMessage: "Who can administer all user groups"}),
        can_manage_billing_group: $t({defaultMessage: "Who can manage plans and billing"}),
        can_create_groups: $t({defaultMessage: "Who can create user groups"}),
        can_move_messages_between_topics_group: $t({
            defaultMessage: "Who can move messages to another topic",
        }),
        can_move_messages_between_channels_group: $t({
            defaultMessage: "Who can move messages to another channel",
        }),
        can_resolve_topics_group: $t({defaultMessage: "Who can resolve topics"}),
        can_delete_any_message_group: $t({defaultMessage: "Who can delete any message"}),
        can_delete_own_message_group: $t({defaultMessage: "Who can delete their own messages"}),
        can_access_all_users_group: $t({
            defaultMessage: "Who can view all other users in the organization",
        }),
        can_summarize_topics_group: $t({defaultMessage: "Who can use AI summaries"}),
        can_create_write_only_bots_group: $t({
            defaultMessage: "Who can create bots that send messages into Zulip",
        }),
        can_create_bots_group: $t({defaultMessage: "Who can create any bot"}),
        can_add_custom_emoji_group: $t({defaultMessage: "Who can add custom emoji"}),
        can_mention_many_users_group: $t({
            defaultMessage: "Who can notify a large number of users with a wildcard mention",
        }),
        can_set_topics_policy_group: new Handlebars.SafeString(
            $t_html({
                defaultMessage:
                    "Who can configure per-channel topic settings <i>(also requires being a channel administrator)</i>",
            }),
        ),
    },
    stream: {
        can_add_subscribers_group: $t({defaultMessage: "Who can subscribe anyone to this channel"}),
        can_move_messages_within_channel_group: $t({
            defaultMessage: "Who can move messages inside this channel",
        }),
        can_send_message_group: $t({defaultMessage: "Who can post to this channel"}),
        can_administer_channel_group: $t({defaultMessage: "Who can administer this channel"}),
        can_subscribe_group: $t({defaultMessage: "Who can subscribe to this channel"}),
        can_remove_subscribers_group: $t({
            defaultMessage: "Who can unsubscribe anyone from this channel",
        }),
    },
    group: {
        can_add_members_group: $t({defaultMessage: "Who can add members to this group"}),
        can_join_group: $t({defaultMessage: "Who can join this group"}),
        can_leave_group: $t({defaultMessage: "Who can leave this group"}),
        can_manage_group: $t({defaultMessage: "Who can administer this group"}),
        can_mention_group: $t({defaultMessage: "Who can mention this group"}),
        can_remove_members_group: $t({defaultMessage: "Who can remove members from this group"}),
    },
};

// Order of subsections and its settings is important here as
// this object is used for rendering the assigned permissions
// in group permissions panel.
export const realm_group_permission_settings: {
    subsection_heading: string;
    subsection_key: string;
    settings: RealmGroupSettingName[];
}[] = [
    {
        subsection_heading: $t({defaultMessage: "Joining the organization"}),
        subsection_key: "org-join-settings",
        settings: ["can_invite_users_group", "create_multiuse_invite_group"],
    },
    {
        subsection_heading: $t({defaultMessage: "Channel permissions"}),
        subsection_key: "org-stream-permissions",
        settings: [
            "can_create_public_channel_group",
            "can_create_web_public_channel_group",
            "can_create_private_channel_group",
            "can_add_subscribers_group",
            "can_mention_many_users_group",
            "can_set_topics_policy_group",
        ],
    },
    {
        subsection_heading: $t({defaultMessage: "Group permissions"}),
        subsection_key: "org-group-permissions",
        settings: ["can_manage_all_groups", "can_create_groups"],
    },
    {
        subsection_heading: $t({defaultMessage: "Direct message permissions"}),
        subsection_key: "org-direct-message-permissions",
        settings: ["direct_message_permission_group", "direct_message_initiator_group"],
    },
    {
        subsection_heading: $t({defaultMessage: "Moving messages"}),
        subsection_key: "org-moving-msgs",
        settings: [
            "can_move_messages_between_topics_group",
            "can_move_messages_between_channels_group",
            "can_resolve_topics_group",
        ],
    },
    {
        subsection_heading: $t({defaultMessage: "Message deletion"}),
        subsection_key: "org-msg-deletion",
        settings: ["can_delete_any_message_group", "can_delete_own_message_group"],
    },
    {
        subsection_heading: $t({defaultMessage: "Guests"}),
        subsection_key: "org-guests-permissions",
        settings: ["can_access_all_users_group"],
    },
    {
        subsection_heading: $t({defaultMessage: "Other permissions"}),
        subsection_key: "org-other-permissions",
        settings: [
            "can_manage_billing_group",
            "can_summarize_topics_group",
            "can_create_write_only_bots_group",
            "can_create_bots_group",
            "can_add_custom_emoji_group",
        ],
    },
];

export const owner_editable_realm_group_permission_settings = new Set([
    "can_create_groups",
    "can_invite_users_group",
    "can_manage_all_groups",
    "create_multiuse_invite_group",
]);

// Order of settings is important, as this list is used to
// render assigned permissions in permissions panel.
export const stream_group_permission_settings: StreamGroupSettingName[] = [
    "can_send_message_group",
    "can_administer_channel_group",
    "can_move_messages_within_channel_group",
    "can_subscribe_group",
    "can_add_subscribers_group",
    "can_remove_subscribers_group",
];

export const stream_group_permission_settings_requiring_content_access: StreamGroupSettingName[] = [
    "can_add_subscribers_group",
    "can_subscribe_group",
];

// Order of settings is important, as this list is used to
// render assigned permissions in permissions panel.
export const group_permission_settings: GroupGroupSettingName[] = [
    "can_manage_group",
    "can_mention_group",
    "can_add_members_group",
    "can_remove_members_group",
    "can_join_group",
    "can_leave_group",
];

// NOTIFICATIONS

export const general_notifications_table_labels = {
    realm: [
        /* An array of notification settings of any category like
         * `stream_notification_settings` which makes a single row of
         * "Notification triggers" table should follow this order
         */
        "visual",
        "audio",
        "mobile",
        "email",
        "all_mentions",
    ],
    stream: [
        ["is_muted", $t({defaultMessage: "Mute channel"})],
        ["desktop_notifications", $t({defaultMessage: "Visual desktop notifications"})],
        ["audible_notifications", $t({defaultMessage: "Audible desktop notifications"})],
        ["push_notifications", $t({defaultMessage: "Mobile notifications"})],
        ["email_notifications", $t({defaultMessage: "Email notifications"})],
        ["pin_to_top", $t({defaultMessage: "Pin channel to top of left sidebar"})],
        [
            "wildcard_mentions_notify",
            $t({defaultMessage: "Notifications for @all/@everyone mentions"}),
        ],
    ] as const,
};

export const stream_specific_notification_settings: (keyof StreamSpecificNotificationSettings)[] = [
    "desktop_notifications",
    "audible_notifications",
    "push_notifications",
    "email_notifications",
    "wildcard_mentions_notify",
];

export const stream_notification_settings: (keyof StreamNotificationSettings)[] = [
    "enable_stream_desktop_notifications",
    "enable_stream_audible_notifications",
    "enable_stream_push_notifications",
    "enable_stream_email_notifications",
    "wildcard_mentions_notify",
];

export const generalize_stream_notification_setting: Record<
    keyof StreamSpecificNotificationSettings,
    keyof StreamNotificationSettings
> = {
    desktop_notifications: "enable_stream_desktop_notifications",
    audible_notifications: "enable_stream_audible_notifications",
    push_notifications: "enable_stream_push_notifications",
    email_notifications: "enable_stream_email_notifications",
    wildcard_mentions_notify: "wildcard_mentions_notify",
};

export const specialize_stream_notification_setting: Record<
    keyof StreamNotificationSettings,
    keyof StreamSpecificNotificationSettings
> = {
    enable_stream_desktop_notifications: "desktop_notifications",
    enable_stream_audible_notifications: "audible_notifications",
    enable_stream_push_notifications: "push_notifications",
    enable_stream_email_notifications: "email_notifications",
    wildcard_mentions_notify: "wildcard_mentions_notify",
};

export const pm_mention_notification_settings: (keyof PmNotificationSettings)[] = [
    "enable_desktop_notifications",
    "enable_sounds",
    "enable_offline_push_notifications",
    "enable_offline_email_notifications",
];

export const followed_topic_notification_settings: (keyof FollowedTopicNotificationSettings)[] = [
    "enable_followed_topic_desktop_notifications",
    "enable_followed_topic_audible_notifications",
    "enable_followed_topic_push_notifications",
    "enable_followed_topic_email_notifications",
    "enable_followed_topic_wildcard_mentions_notify",
];

const desktop_notification_settings = ["pm_content_in_desktop_notifications"];

const mobile_notification_settings = ["enable_online_push_notifications"];

export const email_notifications_batching_period_values = [
    {
        value: 60 * 2,
        description: $t({defaultMessage: "2 minutes"}),
    },
    {
        value: 60 * 5,
        description: $t({defaultMessage: "5 minutes"}),
    },
    {
        value: 60 * 10,
        description: $t({defaultMessage: "10 minutes"}),
    },
    {
        value: 60 * 30,
        description: $t({defaultMessage: "30 minutes"}),
    },
    {
        value: 60 * 60,
        description: $t({defaultMessage: "1 hour"}),
    },
    {
        value: 60 * 60 * 6,
        description: $t({defaultMessage: "6 hours"}),
    },
    {
        value: 60 * 60 * 24,
        description: $t({defaultMessage: "1 day"}),
    },
    {
        value: 60 * 60 * 24 * 7,
        description: $t({defaultMessage: "1 week"}),
    },
    {
        value: "custom_period",
        description: $t({defaultMessage: "Custom"}),
    },
];

const email_message_notification_settings = ["message_content_in_email_notifications"];

const other_email_settings = [
    "enable_digest_emails",
    "enable_login_emails",
    "enable_marketing_emails",
];

const email_notification_settings = [
    ...other_email_settings,
    ...email_message_notification_settings,
];

const other_notification_settings = [
    ...desktop_notification_settings,
    "desktop_icon_count_display",
    ...mobile_notification_settings,
    ...email_notification_settings,
    "email_notifications_batching_period_seconds",
    "realm_name_in_email_notifications_policy",
    "notification_sound",
    "automatically_follow_topics_policy",
    "automatically_unmute_topics_in_muted_streams_policy",
    "automatically_follow_topics_where_mentioned",
];

export const all_notification_settings = [
    ...followed_topic_notification_settings,
    ...other_notification_settings,
    ...pm_mention_notification_settings,
    ...stream_notification_settings,
];

type Settings = UserSettings | RealmDefaultSettings;
type PageParamsItem = keyof Settings;
type NotificationSettingCheckbox = {
    setting_name: string;
    is_disabled: boolean;
    is_checked: boolean;
    is_mobile_checkbox: boolean;
    push_notifications_disabled: boolean;
};

export function get_notifications_table_row_data(
    notify_settings: PageParamsItem[],
    settings_object: Settings,
): NotificationSettingCheckbox[] {
    return general_notifications_table_labels.realm.map((column, index) => {
        const setting_name = notify_settings[index];
        if (setting_name === undefined) {
            return {
                setting_name: "",
                is_disabled: true,
                is_checked: false,
                is_mobile_checkbox: false,
                push_notifications_disabled: false,
            };
        }

        const checked = settings_object[setting_name];
        if (typeof checked !== "boolean") {
            throw new TypeError(`Incorrect setting_name passed: ${setting_name}`);
        }

        const checkbox = {
            setting_name,
            is_disabled: false,
            is_checked: checked,
            is_mobile_checkbox: false,
            push_notifications_disabled: !realm.realm_push_notifications_enabled,
        };
        if (column === "mobile") {
            checkbox.is_disabled = !realm.realm_push_notifications_enabled;
            checkbox.is_mobile_checkbox = true;
        }
        return checkbox;
    });
}

export function get_custom_stream_specific_notifications_table_row_data(): NotificationSettingCheckbox[] {
    // Returns an array of NotificationSettingCheckbox for the special row that
    // allows adding new configuration for a previously uncustomized channel.
    return stream_specific_notification_settings.map((setting_name) => {
        const checkbox = {
            setting_name,
            is_disabled: true,
            is_checked: false,
            is_mobile_checkbox: setting_name === "push_notifications",
            push_notifications_disabled: !realm.realm_push_notifications_enabled,
        };
        return checkbox;
    });
}

export type AllNotifications = {
    general_settings: {
        label: string;
        notification_settings: NotificationSettingCheckbox[];
        help_link?: string;
    }[];
    settings: {
        desktop_notification_settings: string[];
        mobile_notification_settings: string[];
        email_message_notification_settings: string[];
        other_email_settings: string[];
    };
    disabled_notification_settings: {
        push_notifications: boolean;
        enable_online_push_notifications: boolean;
        message_content_in_email_notifications: boolean;
    };
};

export const all_notifications = (settings_object: Settings): AllNotifications => ({
    general_settings: [
        {
            label: $t({defaultMessage: "Channels"}),
            notification_settings: get_notifications_table_row_data(
                stream_notification_settings,
                settings_object,
            ),
        },
        {
            label: $t({defaultMessage: "DMs, mentions, and alerts"}),
            notification_settings: get_notifications_table_row_data(
                pm_mention_notification_settings,
                settings_object,
            ),
        },
        {
            label: $t({defaultMessage: "Followed topics"}),
            notification_settings: get_notifications_table_row_data(
                followed_topic_notification_settings,
                settings_object,
            ),
            help_link: "/help/follow-a-topic",
        },
    ],
    settings: {
        desktop_notification_settings,
        mobile_notification_settings,
        email_message_notification_settings,
        other_email_settings,
    },
    disabled_notification_settings: {
        push_notifications: !realm.realm_push_notifications_enabled,
        enable_online_push_notifications: !realm.realm_push_notifications_enabled,
        message_content_in_email_notifications:
            !realm.realm_message_content_allowed_in_email_notifications,
    },
});

export const realm_name_in_email_notifications_policy_values = {
    automatic: {
        code: 1,
        description: $t({defaultMessage: "Automatic"}),
    },
    always: {
        code: 2,
        description: $t({defaultMessage: "Always"}),
    },
    never: {
        code: 3,
        description: $t({defaultMessage: "Never"}),
    },
};

export const desktop_icon_count_display_values = {
    messages: {
        code: 1,
        description: $t({defaultMessage: "All unread messages"}),
    },
    dm_mention_followed_topic: {
        code: 2,
        description: $t({defaultMessage: "DMs, mentions, and followed topics"}),
    },
    dm_mention: {
        code: 3,
        description: $t({defaultMessage: "DMs and mentions"}),
    },
    none: {
        code: 4,
        description: $t({defaultMessage: "None"}),
    },
};

export const system_user_groups_list = [
    {
        name: "role:internet",
        dropdown_option_name: $t({defaultMessage: "Everyone on the internet"}),
        display_name: $t({defaultMessage: "Everyone on the internet"}),
    },
    {
        name: "role:everyone",
        dropdown_option_name: $t({defaultMessage: "Admins, moderators, members and guests"}),
        display_name: $t({defaultMessage: "Everyone including guests"}),
    },
    {
        name: "role:members",
        dropdown_option_name: $t({defaultMessage: "Admins, moderators and members"}),
        display_name: $t({defaultMessage: "Everyone except guests"}),
    },
    {
        name: "role:fullmembers",
        dropdown_option_name: $t({defaultMessage: "Admins, moderators and full members"}),
        display_name: $t({defaultMessage: "Full members"}),
    },
    {
        name: "role:moderators",
        dropdown_option_name: $t({defaultMessage: "Admins and moderators"}),
        display_name: $t({defaultMessage: "Moderators"}),
    },
    {
        name: "role:administrators",
        dropdown_option_name: $t({defaultMessage: "Admins"}),
        display_name: $t({defaultMessage: "Administrators"}),
    },
    {
        name: "role:owners",
        dropdown_option_name: $t({defaultMessage: "Owners"}),
        display_name: $t({defaultMessage: "Owners"}),
    },
    {
        name: "role:nobody",
        dropdown_option_name: $t({defaultMessage: "Nobody"}),
        display_name: $t({defaultMessage: "Nobody"}),
    },
];

export const alternate_members_group_typeahead_matching_name = $t({defaultMessage: "Members"});

export const user_topic_visibility_policy_values = {
    followed: {
        code: 3,
        description: $t({defaultMessage: "Followed"}),
    },
    muted: {
        code: 1,
        description: $t({defaultMessage: "Muted"}),
    },
    unmuted: {
        code: 2,
        description: $t({defaultMessage: "Unmuted"}),
    },
    inherit: {
        code: 0,
        description: $t({defaultMessage: "Default for channel"}),
    },
};

export const automatically_follow_or_unmute_topics_policy_values = {
    participation: {
        code: 1,
        description: $t({defaultMessage: "Topics I participate in"}),
    },
    send: {
        code: 2,
        description: $t({defaultMessage: "Topics I send a message to"}),
    },
    initiation: {
        code: 3,
        description: $t({defaultMessage: "Topics I start"}),
    },
    never: {
        code: 4,
        description: $t({defaultMessage: "Never"}),
    },
};

export const stream_privacy_policy_values = {
    web_public: {
        code: "web-public",
        name: $t({defaultMessage: "Web-public"}),
        description: $t({
            defaultMessage:
                "Anyone on the internet can view messages; members of your organization can join.",
        }),
    },
    public: {
        code: "public",
        name: $t({defaultMessage: "Public"}),
        description: $t({
            defaultMessage: "Members of your organization can view messages and join",
        }),
    },
    private_with_public_history: {
        code: "invite-only-public-history",
        name: $t({defaultMessage: "Private, shared history"}),
        description: $t({
            defaultMessage: "Joining and viewing messages requires being invited",
        }),
    },
    private: {
        code: "invite-only",
        name: $t({defaultMessage: "Private, protected history"}),
        description: $t({
            defaultMessage:
                "Joining and viewing messages requires being invited; users can only view messages sent while they were subscribed",
        }),
    },
};

export const export_type_values = {
    export_public: {
        value: 1,
        description: $t({defaultMessage: "Public data"}),
        default: false,
    },
    export_full_with_consent: {
        value: 2,
        description: $t({defaultMessage: "Standard"}),
        default: true,
    },
};

export const bot_type_values = {
    default_bot: {
        type_id: 1,
        name: $t({defaultMessage: "Generic bot"}),
    },
    incoming_webhook_bot: {
        type_id: 2,
        name: $t({defaultMessage: "Incoming webhook"}),
    },
    outgoing_webhook_bot: {
        type_id: 3,
        name: $t({defaultMessage: "Outgoing webhook"}),
    },
    embedded_bot: {
        type_id: 4,
        name: $t({defaultMessage: "Embedded bot"}),
    },
};

export const realm_plan_types = {
    self_hosted: {code: 1},
    limited: {code: 2},
    standard: {code: 3},
    standard_free: {code: 4},
    plus: {code: 10},
};

export const no_folder_selected = -1;
