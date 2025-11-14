import * as z from "zod/mini";

import {server_add_bot_schema} from "./bot_types.ts";
import {realm_default_settings_schema} from "./realm_user_settings_defaults.ts";
import {api_stream_subscription_schema, never_subscribed_stream_schema} from "./stream_types.ts";
import {group_setting_value_schema} from "./types.ts";
import {user_settings_schema} from "./user_settings.ts";
import {user_status_schema} from "./user_status_types.ts";

const NOT_TYPED_YET = z.unknown();

const group_permission_setting_schema = z.object({
    require_system_group: z.boolean(),
    allow_internet_group: z.boolean(),
    allow_nobody_group: z.boolean(),
    allow_everyone_group: z.boolean(),
    default_group_name: z.string(),
    default_for_system_groups: z.nullable(z.string()),
    allowed_system_groups: z.array(z.string()),
});
export type GroupPermissionSetting = z.output<typeof group_permission_setting_schema>;

export const narrow_canonical_operator_schema = z.enum([
    "", // Used for search suggestions.
    "channel",
    "channels",
    "dm",
    "dm-including",
    "has",
    "id",
    "in",
    "is",
    "near",
    "search",
    "sender",
    "topic",
    "with",
]);
export type NarrowCanonicalOperator = z.output<typeof narrow_canonical_operator_schema>;

const narrow_legacy_operator_schema = z.enum([
    "pm-with",
    "group-pm-with",
    "from",
    "stream",
    "streams",
    "subject",
]);

export const narrow_operator_schema = z.union([
    narrow_canonical_operator_schema,
    narrow_legacy_operator_schema,
]);
export type NarrowOperator = z.output<typeof narrow_operator_schema>;

export const narrow_canonical_term_schema = z.object({
    negated: z.optional(z.boolean()),
    operator: narrow_canonical_operator_schema,
    operand: z.string(),
});
export type NarrowCanonicalTerm = z.output<typeof narrow_canonical_term_schema>;

export const narrow_term_schema = z.union([
    narrow_canonical_term_schema,
    z.object({
        negated: z.optional(z.boolean()),
        operator: narrow_legacy_operator_schema,
        operand: z.string(),
    }),
]);
export type NarrowTerm = z.output<typeof narrow_term_schema>;

export const custom_profile_field_schema = z.object({
    display_in_profile_summary: z.optional(z.boolean()),
    editable_by_user: z.boolean(),
    field_data: z.string(),
    hint: z.string(),
    id: z.number(),
    name: z.string(),
    order: z.number(),
    required: z.boolean(),
    type: z.number(),
});

export type CustomProfileField = z.output<typeof custom_profile_field_schema>;

export const scheduled_message_schema = z.intersection(
    z.object({
        scheduled_message_id: z.number(),
        content: z.string(),
        rendered_content: z.string(),
        scheduled_delivery_timestamp: z.number(),
        failed: z.boolean(),
    }),
    z.discriminatedUnion("type", [
        z.object({
            type: z.literal("private"),
            to: z.array(z.number()),
        }),
        z.object({
            type: z.literal("stream"),
            to: z.number(),
            topic: z.string(),
        }),
    ]),
);

export const reminder_schema = z.object({
    reminder_id: z.number(),
    type: z.literal("private"),
    to: z.array(z.number()),
    content: z.string(),
    rendered_content: z.string(),
    scheduled_delivery_timestamp: z.number(),
    failed: z.boolean(),
    reminder_target_message_id: z.number(),
});

export const profile_datum_schema = z.object({
    value: z.string(),
    rendered_value: z.nullish(z.string()),
});

export const user_schema = z.intersection(
    z.object({
        user_id: z.number(),
        delivery_email: z.nullable(z.string()),
        email: z.string(),
        full_name: z.string(),
        // used for caching result of remove_diacritics.
        name_with_diacritics_removed: z.optional(z.string()),
        date_joined: z.string(),
        is_active: z.optional(z.boolean()),
        is_owner: z.boolean(),
        is_admin: z.boolean(),
        is_guest: z.boolean(),
        is_moderator: z.optional(z.boolean()),
        role: z.number(),
        timezone: z.optional(z.string()),
        avatar_url: z.nullish(z.string()),
        avatar_version: z.number(),
        profile_data: z.optional(z.record(z.coerce.number<string>(), profile_datum_schema)),
        // used for fake user objects.
        is_missing_server_data: z.optional(z.boolean()),
        // used for inaccessible user objects.
        is_inaccessible_user: z.optional(z.boolean()),
        is_system_bot: z.optional(z.literal(true)),
    }),
    z.discriminatedUnion("is_bot", [
        z.object({
            is_bot: z.literal(false),
            bot_type: z.optional(z.null()),
        }),
        z.object({
            is_bot: z.literal(true),
            bot_type: z.number(),
            bot_owner_id: z.nullable(z.number()),
        }),
    ]),
);

export const server_emoji_schema = z.object({
    id: z.string(),
    author_id: z.number(),
    deactivated: z.boolean(),
    name: z.string(),
    source_url: z.string(),
    still_url: z.nullable(z.string()),

    // Added later in `settings_emoji.ts` when setting up the emoji settings.
    author: z.nullish(user_schema),
});

export const realm_emoji_map_schema = z.record(z.string(), server_emoji_schema);

export type GroupSettingValue = z.infer<typeof group_setting_value_schema>;

export const raw_user_group_schema = z.object({
    description: z.string(),
    id: z.number(),
    creator_id: z.nullable(z.number()),
    date_created: z.nullable(z.number()),
    name: z.string(),
    members: z.array(z.number()),
    is_system_group: z.boolean(),
    direct_subgroup_ids: z.array(z.number()),
    can_add_members_group: group_setting_value_schema,
    can_join_group: group_setting_value_schema,
    can_leave_group: group_setting_value_schema,
    can_manage_group: group_setting_value_schema,
    can_mention_group: group_setting_value_schema,
    can_remove_members_group: group_setting_value_schema,
    deactivated: z.boolean(),
});

export const channel_folder_schema = z.object({
    id: z.number(),
    name: z.string(),
    description: z.string(),
    rendered_description: z.string(),
    creator_id: z.nullable(z.number()),
    date_created: z.number(),
    is_archived: z.boolean(),
    order: z.number(),
});

export const navigation_view_schema = z.object({
    fragment: z.string(),
    name: z.string(),
    is_pinned: z.boolean(),
});

export const user_topic_schema = z.object({
    stream_id: z.number(),
    topic_name: z.string(),
    last_updated: z.number(),
    visibility_policy: z.number(),
});

export const muted_user_schema = z.object({
    id: z.number(),
    timestamp: z.number(),
});

const unread_stream_info_schema = z.object({
    stream_id: z.number(),
    topic: z.string(),
    unread_message_ids: z.array(z.number()),
});

export const unread_direct_message_info_schema = z.object({
    other_user_id: z.number(),
    unread_message_ids: z.array(z.number()),
});

export const unread_direct_message_group_info_schema = z.object({
    user_ids_string: z.string(),
    unread_message_ids: z.array(z.number()),
});

export const presence_schema = z.object({
    active_timestamp: z.optional(z.number()),
    idle_timestamp: z.optional(z.number()),
});

export const realm_billing_schema = z.object({
    has_pending_sponsorship_request: z.boolean(),
});

export const saved_snippet_schema = z.object({
    id: z.number(),
    title: z.string(),
    content: z.string(),
    date_created: z.number(),
});

const one_time_notice_schema = z.object({
    name: z.string(),
    type: z.literal("one_time_notice"),
});

const one_time_action_schema = z.object({
    name: z.string(),
    type: z.literal("one_time_action"),
});

export const thumbnail_format_schema = z.object({
    name: z.string(),
    max_width: z.number(),
    max_height: z.number(),
    format: z.string(),
    animated: z.boolean(),
});

export const onboarding_step_schema = z.union([one_time_notice_schema, one_time_action_schema]);

// Sync this with zerver.lib.events.do_events_register.
const current_user_schema = z.object({
    avatar_source: z.string(),
    avatar_url: z.nullish(z.string()),
    avatar_url_medium: z.nullish(z.string()),
    can_create_private_streams: z.boolean(),
    can_create_public_streams: z.boolean(),
    can_create_streams: z.boolean(),
    can_create_web_public_streams: z.boolean(),
    can_invite_others_to_realm: z.boolean(),
    delivery_email: z.string(),
    email: z.string(),
    full_name: z.string(),
    has_zoom_token: z.boolean(),
    is_admin: z.boolean(),
    is_guest: z.boolean(),
    is_moderator: z.boolean(),
    is_owner: z.boolean(),
    user_id: z.number(),
});

const custom_profile_field_types_schema = z.object({
    SHORT_TEXT: z.object({id: z.number(), name: z.string()}),
    LONG_TEXT: z.object({id: z.number(), name: z.string()}),
    DATE: z.object({id: z.number(), name: z.string()}),
    SELECT: z.object({id: z.number(), name: z.string()}),
    URL: z.object({id: z.number(), name: z.string()}),
    EXTERNAL_ACCOUNT: z.object({id: z.number(), name: z.string()}),
    USER: z.object({id: z.number(), name: z.string()}),
    PRONOUNS: z.object({id: z.number(), name: z.string()}),
});

export type CustomProfileFieldTypes = z.infer<typeof custom_profile_field_types_schema>;

export const realm_domain_schema = z.object({
    domain: z.string(),
    allow_subdomains: z.boolean(),
});

export const realm_playground_schema = z.object({
    id: z.number(),
    name: z.string(),
    pygments_language: z.string(),
    url_template: z.string(),
});

export const realm_linkifier_schema = z.object({
    pattern: z.string(),
    url_template: z.string(),
    id: z.number(),
});

export const realm_report_message_types = z.object({
    key: z.string(),
    name: z.string(),
});

// Sync this with zerver.lib.events.do_events_register.
export const realm_schema = z.object({
    custom_profile_fields: z.array(custom_profile_field_schema),
    custom_profile_field_types: custom_profile_field_types_schema,
    demo_organization_scheduled_deletion_date: z.optional(z.number()),
    giphy_api_key: z.string(),
    giphy_rating_options: z.intersection(
        z.record(z.string(), z.object({id: z.number(), name: z.string()})),
        z.object({disabled: z.object({id: z.number(), name: z.string()})}),
    ),
    max_avatar_file_size_mib: z.number(),
    max_channel_folder_description_length: z.number(),
    max_channel_folder_name_length: z.number(),
    max_file_upload_size_mib: z.number(),
    max_icon_file_size_mib: z.number(),
    max_logo_file_size_mib: z.number(),
    max_message_length: z.number(),
    max_reminder_note_length: z.number(),
    max_stream_description_length: z.number(),
    max_stream_name_length: z.number(),
    max_topic_length: z.number(),
    max_bulk_new_subscription_messages: z.number(),
    password_min_guesses: z.number(),
    password_min_length: z.number(),
    password_max_length: z.number(),
    realm_allow_message_editing: z.boolean(),
    realm_authentication_methods: z.record(
        z.string(),
        z.object({
            enabled: z.boolean(),
            available: z.boolean(),
            unavailable_reason: z.optional(z.string()),
        }),
    ),
    realm_available_video_chat_providers: z.object({
        disabled: z.object({name: z.string(), id: z.number()}),
        jitsi_meet: z.object({name: z.string(), id: z.number()}),
        zoom: z.optional(z.object({name: z.string(), id: z.number()})),
        zoom_server_to_server: z.optional(z.object({name: z.string(), id: z.number()})),
        big_blue_button: z.optional(z.object({name: z.string(), id: z.number()})),
    }),
    realm_avatar_changes_disabled: z.boolean(),
    realm_bot_domain: z.string(),
    realm_can_access_all_users_group: z.number(),
    realm_can_add_custom_emoji_group: group_setting_value_schema,
    realm_can_add_subscribers_group: group_setting_value_schema,
    realm_can_create_bots_group: group_setting_value_schema,
    realm_can_create_groups: group_setting_value_schema,
    realm_can_create_public_channel_group: group_setting_value_schema,
    realm_can_create_private_channel_group: group_setting_value_schema,
    realm_can_create_web_public_channel_group: z.number(),
    realm_can_create_write_only_bots_group: group_setting_value_schema,
    realm_can_delete_any_message_group: group_setting_value_schema,
    realm_can_delete_own_message_group: group_setting_value_schema,
    realm_can_invite_users_group: group_setting_value_schema,
    realm_can_manage_all_groups: group_setting_value_schema,
    realm_can_manage_billing_group: group_setting_value_schema,
    realm_can_mention_many_users_group: group_setting_value_schema,
    realm_can_move_messages_between_channels_group: group_setting_value_schema,
    realm_can_move_messages_between_topics_group: group_setting_value_schema,
    realm_can_resolve_topics_group: group_setting_value_schema,
    realm_can_set_delete_message_policy_group: group_setting_value_schema,
    realm_can_set_topics_policy_group: group_setting_value_schema,
    realm_can_summarize_topics_group: group_setting_value_schema,
    realm_create_multiuse_invite_group: group_setting_value_schema,
    realm_date_created: z.number(),
    realm_default_code_block_language: z.string(),
    realm_default_external_accounts: z.record(
        z.string(),
        z.object({
            text: z.string(),
            url_pattern: z.string(),
            name: z.string(),
            hint: z.string(),
        }),
    ),
    realm_default_language: z.string(),
    realm_description: z.string(),
    realm_digest_emails_enabled: z.boolean(),
    realm_digest_weekday: z.number(),
    realm_direct_message_initiator_group: group_setting_value_schema,
    realm_direct_message_permission_group: group_setting_value_schema,
    realm_disallow_disposable_email_addresses: z.boolean(),
    realm_domains: z.array(realm_domain_schema),
    realm_email_auth_enabled: z.boolean(),
    realm_email_changes_disabled: z.boolean(),
    realm_emails_restricted_to_domains: z.boolean(),
    realm_embedded_bots: z.array(
        z.object({
            name: z.string(),
            config: z.record(z.string(), z.string()),
        }),
    ),
    realm_empty_topic_display_name: z.string(),
    realm_enable_guest_user_dm_warning: z.boolean(),
    realm_enable_guest_user_indicator: z.boolean(),
    realm_enable_read_receipts: z.boolean(),
    realm_enable_spectator_access: z.boolean(),
    realm_giphy_rating: z.number(),
    realm_icon_source: z.string(),
    realm_icon_url: z.string(),
    realm_incoming_webhook_bots: z.array(
        z.object({
            display_name: z.string(),
            name: z.string(),
            all_event_types: z.nullable(z.array(z.string())),
            config_options: z.optional(
                z.array(
                    z.object({
                        key: z.string(),
                        label: z.string(),
                        validator: z.string(),
                    }),
                ),
            ),
            url_options: z.optional(
                z.array(
                    z.object({
                        key: z.string(),
                        label: z.string(),
                        validator: z.string(),
                    }),
                ),
            ),
        }),
    ),
    realm_inline_image_preview: z.boolean(),
    realm_inline_url_embed_preview: z.boolean(),
    realm_invite_required: z.boolean(),
    realm_jitsi_server_url: z.nullable(z.string()),
    realm_linkifiers: z.array(realm_linkifier_schema),
    realm_logo_source: z.string(),
    realm_logo_url: z.string(),
    realm_message_content_allowed_in_email_notifications: z.boolean(),
    realm_message_content_edit_limit_seconds: z.nullable(z.number()),
    realm_message_content_delete_limit_seconds: z.nullable(z.number()),
    realm_message_edit_history_visibility_policy: z.enum(["all", "moves", "none"]),
    realm_message_retention_days: z.number(),
    realm_moderation_request_channel_id: z.number(),
    realm_move_messages_between_streams_limit_seconds: z.nullable(z.number()),
    realm_move_messages_within_stream_limit_seconds: z.nullable(z.number()),
    realm_name_changes_disabled: z.boolean(),
    realm_name: z.string(),
    realm_new_stream_announcements_stream_id: z.number(),
    realm_night_logo_source: z.string(),
    realm_night_logo_url: z.string(),
    realm_org_type: z.number(),
    realm_password_auth_enabled: z.boolean(),
    realm_plan_type: z.number(),
    realm_playgrounds: z.array(realm_playground_schema),
    realm_presence_disabled: z.boolean(),
    realm_push_notifications_enabled: z.boolean(),
    realm_push_notifications_enabled_end_timestamp: z.nullable(z.number()),
    realm_require_e2ee_push_notifications: z.boolean(),
    realm_require_unique_names: z.boolean(),
    realm_send_channel_events_messages: z.boolean(),
    realm_send_welcome_emails: z.boolean(),
    realm_signup_announcements_stream_id: z.number(),
    realm_topics_policy: z.enum(["allow_empty_topic", "disable_empty_topic"]),
    realm_upload_quota_mib: z.nullable(z.number()),
    realm_url: z.string(),
    realm_video_chat_provider: z.number(),
    realm_waiting_period_threshold: z.number(),
    realm_want_advertise_in_communities_directory: z.boolean(),
    realm_welcome_message_custom_text: z.string(),
    realm_zulip_update_announcements_stream_id: z.number(),
    server_avatar_changes_disabled: z.boolean(),
    server_can_summarize_topics: z.boolean(),
    server_emoji_data_url: z.string(),
    server_inline_image_preview: z.boolean(),
    server_inline_url_embed_preview: z.boolean(),
    server_max_deactivated_realm_deletion_days: z.nullable(z.number()),
    server_min_deactivated_realm_deletion_days: z.nullable(z.number()),
    server_jitsi_server_url: z.nullable(z.string()),
    server_name_changes_disabled: z.boolean(),
    server_needs_upgrade: z.boolean(),
    server_presence_offline_threshold_seconds: z.number(),
    server_presence_ping_interval_seconds: z.number(),
    server_report_message_types: z.array(realm_report_message_types),
    server_supported_permission_settings: z.object({
        realm: z.record(z.string(), group_permission_setting_schema),
        stream: z.record(z.string(), group_permission_setting_schema),
        group: z.record(z.string(), group_permission_setting_schema),
    }),
    server_thumbnail_formats: z.array(thumbnail_format_schema),
    server_typing_started_expiry_period_milliseconds: z.number(),
    server_typing_started_wait_period_milliseconds: z.number(),
    server_typing_stopped_wait_period_milliseconds: z.number(),
    server_web_public_streams_enabled: z.boolean(),
    settings_send_digest_emails: z.boolean(),
    stop_words: z.array(z.string()),
    upgrade_text_for_wide_organization_logo: z.string(),
    zulip_feature_level: z.number(),
    zulip_merge_base: z.string(),
    zulip_plan_is_not_limited: z.boolean(),
    zulip_version: z.string(),
});

export const split_state_data_schema = z.object({
    alert_words: z.object({alert_words: z.array(z.string())}),
    emoji: z.object({realm_emoji: realm_emoji_map_schema}),
    realm_billing: z.object({realm_billing: realm_billing_schema}),
    bot: z.object({realm_bots: z.array(server_add_bot_schema)}),
    people: z.object({
        realm_users: z.array(user_schema),
        realm_non_active_users: z.array(user_schema),
        cross_realm_bots: z.array(user_schema),
    }),
    pm_conversations: z.object({
        recent_private_conversations: z.array(
            z.object({
                max_message_id: z.number(),
                user_ids: z.array(z.number()),
            }),
        ),
    }),
    presence: z.object({
        presences: z.record(z.coerce.number<string>(), presence_schema),
        server_timestamp: z.number(),
        presence_last_update_id: z.optional(z.number()),
    }),
    saved_snippets: z.object({saved_snippets: z.array(saved_snippet_schema)}),
    starred_messages: z.object({starred_messages: z.array(z.number())}),
    stream_data: z.object({
        subscriptions: z.array(api_stream_subscription_schema),
        unsubscribed: z.array(api_stream_subscription_schema),
        never_subscribed: z.array(never_subscribed_stream_schema),
        realm_default_streams: z.array(z.number()),
    }),
    user_groups: z.object({realm_user_groups: z.array(raw_user_group_schema)}),
    channel_folders: z.object({channel_folders: z.array(channel_folder_schema)}),
    unread: z.object({
        unread_msgs: z.object({
            pms: z.array(unread_direct_message_info_schema),
            streams: z.array(unread_stream_info_schema),
            huddles: z.array(unread_direct_message_group_info_schema),
            mentions: z.array(z.number()),
            count: z.number(),
            old_unreads_missing: z.boolean(),
        }),
    }),
    muted_users: z.object({muted_users: z.array(muted_user_schema)}),
    user_topics: z.object({user_topics: z.array(user_topic_schema)}),
    user_status: z.object({user_status: z.record(z.string(), user_status_schema)}),
    user_settings: z.object({user_settings: user_settings_schema}),
    realm_settings_defaults: z.object({
        realm_user_settings_defaults: realm_default_settings_schema,
    }),
    scheduled_messages: z.object({scheduled_messages: z.array(scheduled_message_schema)}),
    reminders: z.object({reminders: z.array(reminder_schema)}),
    server_events_state: z.object({
        queue_id: z.nullable(z.string()),
    }),
    server_events: z.object({
        server_generation: NOT_TYPED_YET,
        event_queue_longpoll_timeout_seconds: NOT_TYPED_YET,
        last_event_id: NOT_TYPED_YET,
    }),
    local_message: z.object({max_message_id: z.number()}),
    onboarding_steps: z.object({
        onboarding_steps: z.array(onboarding_step_schema),
        navigation_tour_video_url: z.nullable(z.string()),
    }),
    current_user: current_user_schema,
    realm: realm_schema,
    navigation_views: z.object({navigation_views: z.array(navigation_view_schema)}),
});
type SplitStateDataInput = z.input<typeof split_state_data_schema>;

export const state_data_schema = z.pipe(
    z.transform((state_data: SplitStateDataInput[keyof SplitStateDataInput]) =>
        Object.fromEntries(
            Object.keys(split_state_data_schema.shape).map((part) => [part, state_data]),
        ),
    ),
    split_state_data_schema,
);
export type StateData = z.infer<typeof state_data_schema>;

export type CurrentUser = StateData["current_user"];
export type Realm = StateData["realm"];
export type RealmBilling = StateData["realm_billing"]["realm_billing"];

export let current_user: CurrentUser;
export let realm: Realm;
export let realm_billing: RealmBilling;

export function set_current_user(initial_current_user: CurrentUser): void {
    current_user = initial_current_user;
}

export function set_realm(initial_realm: Realm): void {
    realm = initial_realm;
}

export function set_realm_billing(params: StateData["realm_billing"]): void {
    realm_billing = params.realm_billing;
}
