import * as v from "valibot";

import {server_add_bot_schema} from "./bot_types.ts";
import {realm_default_settings_schema} from "./realm_user_settings_defaults.ts";
import {api_stream_subscription_schema, never_subscribed_stream_schema} from "./stream_types.ts";
import {group_setting_value_schema} from "./types.ts";
import {user_settings_schema} from "./user_settings.ts";
import {user_status_schema} from "./user_status_types.ts";

const NOT_TYPED_YET = v.optional(v.unknown());

const group_permission_setting_schema = v.object({
    require_system_group: v.boolean(),
    allow_internet_group: v.boolean(),
    allow_nobody_group: v.boolean(),
    allow_everyone_group: v.boolean(),
    default_group_name: v.string(),
    default_for_system_groups: v.nullable(v.string()),
    allowed_system_groups: v.array(v.string()),
});
export type GroupPermissionSetting = v.InferOutput<typeof group_permission_setting_schema>;

export const narrow_term_schema = v.object({
    negated: v.optional(v.boolean()),
    operator: v.string(),
    operand: v.string(),
});
export type NarrowTerm = v.InferOutput<typeof narrow_term_schema>;

export const custom_profile_field_schema = v.object({
    display_in_profile_summary: v.optional(v.boolean()),
    editable_by_user: v.boolean(),
    field_data: v.string(),
    hint: v.string(),
    id: v.number(),
    name: v.string(),
    order: v.number(),
    required: v.boolean(),
    type: v.number(),
});

export type CustomProfileField = v.InferOutput<typeof custom_profile_field_schema>;

export const scheduled_message_schema = v.intersect([
    v.object({
        scheduled_message_id: v.number(),
        content: v.string(),
        rendered_content: v.string(),
        scheduled_delivery_timestamp: v.number(),
        failed: v.boolean(),
    }),
    v.variant("type", [
        v.object({
            type: v.literal("private"),
            to: v.array(v.number()),
        }),
        v.object({
            type: v.literal("stream"),
            to: v.number(),
            topic: v.string(),
        }),
    ]),
]);

export const profile_datum_schema = v.object({
    value: v.string(),
    rendered_value: v.nullish(v.string()),
});

export const user_schema = v.intersect([
    v.object({
        user_id: v.number(),
        delivery_email: v.nullable(v.string()),
        email: v.string(),
        full_name: v.string(),
        // used for caching result of remove_diacritics.
        name_with_diacritics_removed: v.optional(v.string()),
        date_joined: v.string(),
        is_active: v.optional(v.boolean()),
        is_owner: v.boolean(),
        is_admin: v.boolean(),
        is_guest: v.boolean(),
        is_moderator: v.optional(v.boolean()),
        is_billing_admin: v.optional(v.boolean()),
        role: v.number(),
        timezone: v.optional(v.string()),
        avatar_url: v.nullish(v.string()),
        avatar_version: v.number(),
        profile_data: v.optional(
            v.record(v.pipe(v.string(), v.transform(Number), v.number()), profile_datum_schema),
        ),
        // used for fake user objects.
        is_missing_server_data: v.optional(v.boolean()),
        // used for inaccessible user objects.
        is_inaccessible_user: v.optional(v.boolean()),
        is_system_bot: v.optional(v.literal(true)),
    }),
    v.variant("is_bot", [
        v.object({
            is_bot: v.literal(false),
            bot_type: v.optional(v.null()),
        }),
        v.object({
            is_bot: v.literal(true),
            bot_type: v.number(),
            bot_owner_id: v.nullable(v.number()),
        }),
    ]),
]);

export const server_emoji_schema = v.object({
    id: v.string(),
    author_id: v.number(),
    deactivated: v.boolean(),
    name: v.string(),
    source_url: v.string(),
    still_url: v.nullable(v.string()),

    // Added later in `settings_emoji.ts` when setting up the emoji settings.
    author: v.nullish(user_schema),
});

export const realm_emoji_map_schema = v.record(v.string(), server_emoji_schema);

export type GroupSettingValue = v.InferOutput<typeof group_setting_value_schema>;

export const raw_user_group_schema = v.object({
    description: v.string(),
    id: v.number(),
    creator_id: v.nullable(v.number()),
    date_created: v.nullable(v.number()),
    name: v.string(),
    members: v.array(v.number()),
    is_system_group: v.boolean(),
    direct_subgroup_ids: v.array(v.number()),
    can_add_members_group: group_setting_value_schema,
    can_join_group: group_setting_value_schema,
    can_leave_group: group_setting_value_schema,
    can_manage_group: group_setting_value_schema,
    can_mention_group: group_setting_value_schema,
    can_remove_members_group: group_setting_value_schema,
    deactivated: v.boolean(),
});

export const user_topic_schema = v.object({
    stream_id: v.number(),
    topic_name: v.string(),
    last_updated: v.number(),
    visibility_policy: v.number(),
});

export const muted_user_schema = v.object({
    id: v.number(),
    timestamp: v.number(),
});

const unread_stream_info_schema = v.object({
    stream_id: v.number(),
    topic: v.string(),
    unread_message_ids: v.array(v.number()),
});

export const unread_direct_message_info_schema = v.object({
    other_user_id: v.number(),
    unread_message_ids: v.array(v.number()),
});

export const unread_direct_message_group_info_schema = v.object({
    user_ids_string: v.string(),
    unread_message_ids: v.array(v.number()),
});

export const presence_schema = v.object({
    active_timestamp: v.optional(v.number()),
    idle_timestamp: v.optional(v.number()),
});

export const saved_snippet_schema = v.object({
    id: v.number(),
    title: v.string(),
    content: v.string(),
    date_created: v.number(),
});

const one_time_notice_schema = v.object({
    name: v.string(),
    type: v.literal("one_time_notice"),
});

const one_time_action_schema = v.object({
    name: v.string(),
    type: v.literal("one_time_action"),
});

export const thumbnail_format_schema = v.object({
    name: v.string(),
    max_width: v.number(),
    max_height: v.number(),
    format: v.string(),
    animated: v.boolean(),
});

export const onboarding_step_schema = v.union([one_time_notice_schema, one_time_action_schema]);

// Sync this with zerver.lib.events.do_events_register.
const current_user_schema = v.object({
    avatar_source: v.string(),
    avatar_url: v.nullish(v.string()),
    avatar_url_medium: v.nullish(v.string()),
    can_create_private_streams: v.boolean(),
    can_create_public_streams: v.boolean(),
    can_create_streams: v.boolean(),
    can_create_web_public_streams: v.boolean(),
    can_invite_others_to_realm: v.boolean(),
    delivery_email: v.string(),
    email: v.string(),
    full_name: v.string(),
    has_zoom_token: v.boolean(),
    is_admin: v.boolean(),
    is_billing_admin: v.boolean(),
    is_guest: v.boolean(),
    is_moderator: v.boolean(),
    is_owner: v.boolean(),
    user_id: v.number(),
});

const custom_profile_field_types_schema = v.object({
    SHORT_TEXT: v.object({id: v.number(), name: v.string()}),
    LONG_TEXT: v.object({id: v.number(), name: v.string()}),
    DATE: v.object({id: v.number(), name: v.string()}),
    SELECT: v.object({id: v.number(), name: v.string()}),
    URL: v.object({id: v.number(), name: v.string()}),
    EXTERNAL_ACCOUNT: v.object({id: v.number(), name: v.string()}),
    USER: v.object({id: v.number(), name: v.string()}),
    PRONOUNS: v.object({id: v.number(), name: v.string()}),
});

export type CustomProfileFieldTypes = v.InferOutput<typeof custom_profile_field_types_schema>;

export const realm_domain_schema = v.object({
    domain: v.string(),
    allow_subdomains: v.boolean(),
});

export const realm_playground_schema = v.object({
    id: v.number(),
    name: v.string(),
    pygments_language: v.string(),
    url_template: v.string(),
});

export const realm_linkifier_schema = v.object({
    pattern: v.string(),
    url_template: v.string(),
    id: v.number(),
});

// Sync this with zerver.lib.events.do_events_register.
export const realm_schema = v.object({
    custom_profile_fields: v.array(custom_profile_field_schema),
    custom_profile_field_types: custom_profile_field_types_schema,
    demo_organization_scheduled_deletion_date: v.optional(v.number()),
    giphy_api_key: v.string(),
    giphy_rating_options: v.intersect([
        v.record(v.string(), v.object({id: v.number(), name: v.string()})),
        v.object({disabled: v.object({id: v.number(), name: v.string()})}),
    ]),
    max_avatar_file_size_mib: v.number(),
    max_file_upload_size_mib: v.number(),
    max_icon_file_size_mib: v.number(),
    max_logo_file_size_mib: v.number(),
    max_message_length: v.number(),
    max_stream_description_length: v.number(),
    max_stream_name_length: v.number(),
    max_topic_length: v.number(),
    password_min_guesses: v.number(),
    password_min_length: v.number(),
    password_max_length: v.number(),
    realm_allow_edit_history: v.boolean(),
    realm_allow_message_editing: v.boolean(),
    realm_authentication_methods: v.record(
        v.string(),
        v.object({
            enabled: v.boolean(),
            available: v.boolean(),
            unavailable_reason: v.optional(v.string()),
        }),
    ),
    realm_available_video_chat_providers: v.object({
        disabled: v.object({name: v.string(), id: v.number()}),
        jitsi_meet: v.object({name: v.string(), id: v.number()}),
        zoom: v.optional(v.object({name: v.string(), id: v.number()})),
        big_blue_button: v.optional(v.object({name: v.string(), id: v.number()})),
    }),
    realm_avatar_changes_disabled: v.boolean(),
    realm_bot_creation_policy: v.number(),
    realm_bot_domain: v.string(),
    realm_can_access_all_users_group: v.number(),
    realm_can_add_custom_emoji_group: group_setting_value_schema,
    realm_can_add_subscribers_group: group_setting_value_schema,
    realm_can_create_groups: group_setting_value_schema,
    realm_can_create_public_channel_group: group_setting_value_schema,
    realm_can_create_private_channel_group: group_setting_value_schema,
    realm_can_create_web_public_channel_group: v.number(),
    realm_can_delete_any_message_group: group_setting_value_schema,
    realm_can_delete_own_message_group: group_setting_value_schema,
    realm_can_invite_users_group: group_setting_value_schema,
    realm_can_manage_all_groups: group_setting_value_schema,
    realm_can_move_messages_between_channels_group: group_setting_value_schema,
    realm_can_move_messages_between_topics_group: group_setting_value_schema,
    realm_create_multiuse_invite_group: group_setting_value_schema,
    realm_date_created: v.number(),
    realm_default_code_block_language: v.string(),
    realm_default_external_accounts: v.record(
        v.string(),
        v.object({
            text: v.string(),
            url_pattern: v.string(),
            name: v.string(),
            hint: v.string(),
        }),
    ),
    realm_default_language: v.string(),
    realm_description: v.string(),
    realm_digest_emails_enabled: v.boolean(),
    realm_digest_weekday: v.number(),
    realm_direct_message_initiator_group: group_setting_value_schema,
    realm_direct_message_permission_group: group_setting_value_schema,
    realm_disallow_disposable_email_addresses: v.boolean(),
    realm_domains: v.array(realm_domain_schema),
    realm_email_auth_enabled: v.boolean(),
    realm_email_changes_disabled: v.boolean(),
    realm_emails_restricted_to_domains: v.boolean(),
    realm_embedded_bots: v.array(
        v.object({
            name: v.string(),
            config: v.record(v.string(), v.string()),
        }),
    ),
    realm_empty_topic_display_name: v.string(),
    realm_enable_guest_user_indicator: v.boolean(),
    realm_enable_read_receipts: v.boolean(),
    realm_enable_spectator_access: v.boolean(),
    realm_giphy_rating: v.number(),
    realm_icon_source: v.string(),
    realm_icon_url: v.string(),
    realm_incoming_webhook_bots: v.array(
        v.object({
            display_name: v.string(),
            name: v.string(),
            all_event_types: v.nullable(v.array(v.string())),
            config_options: v.optional(
                v.array(
                    v.object({
                        key: v.string(),
                        label: v.string(),
                        validator: v.string(),
                    }),
                ),
            ),
        }),
    ),
    realm_inline_image_preview: v.boolean(),
    realm_inline_url_embed_preview: v.boolean(),
    realm_invite_required: v.boolean(),
    realm_is_zephyr_mirror_realm: v.boolean(),
    realm_jitsi_server_url: v.nullable(v.string()),
    realm_linkifiers: v.array(realm_linkifier_schema),
    realm_logo_source: v.string(),
    realm_logo_url: v.string(),
    realm_mandatory_topics: v.boolean(),
    realm_message_content_allowed_in_email_notifications: v.boolean(),
    realm_message_content_edit_limit_seconds: v.nullable(v.number()),
    realm_message_content_delete_limit_seconds: v.nullable(v.number()),
    realm_message_retention_days: v.number(),
    realm_move_messages_between_streams_limit_seconds: v.nullable(v.number()),
    realm_move_messages_within_stream_limit_seconds: v.nullable(v.number()),
    realm_name_changes_disabled: v.boolean(),
    realm_name: v.string(),
    realm_new_stream_announcements_stream_id: v.number(),
    realm_night_logo_source: v.string(),
    realm_night_logo_url: v.string(),
    realm_org_type: v.number(),
    realm_password_auth_enabled: v.boolean(),
    realm_plan_type: v.number(),
    realm_playgrounds: v.array(realm_playground_schema),
    realm_presence_disabled: v.boolean(),
    realm_push_notifications_enabled: v.boolean(),
    realm_push_notifications_enabled_end_timestamp: v.nullable(v.number()),
    realm_require_unique_names: v.boolean(),
    realm_send_welcome_emails: v.boolean(),
    realm_signup_announcements_stream_id: v.number(),
    realm_upload_quota_mib: v.nullable(v.number()),
    realm_url: v.string(),
    realm_video_chat_provider: v.number(),
    realm_waiting_period_threshold: v.number(),
    realm_want_advertise_in_communities_directory: v.boolean(),
    realm_wildcard_mention_policy: v.number(),
    realm_zulip_update_announcements_stream_id: v.number(),
    server_avatar_changes_disabled: v.boolean(),
    server_emoji_data_url: v.string(),
    server_inline_image_preview: v.boolean(),
    server_inline_url_embed_preview: v.boolean(),
    server_max_deactivated_realm_deletion_days: v.nullable(v.number()),
    server_min_deactivated_realm_deletion_days: v.nullable(v.number()),
    server_jitsi_server_url: v.nullable(v.string()),
    server_name_changes_disabled: v.boolean(),
    server_needs_upgrade: v.boolean(),
    server_presence_offline_threshold_seconds: v.number(),
    server_presence_ping_interval_seconds: v.number(),
    server_supported_permission_settings: v.object({
        realm: v.record(v.string(), group_permission_setting_schema),
        stream: v.record(v.string(), group_permission_setting_schema),
        group: v.record(v.string(), group_permission_setting_schema),
    }),
    server_thumbnail_formats: v.array(thumbnail_format_schema),
    server_typing_started_expiry_period_milliseconds: v.number(),
    server_typing_started_wait_period_milliseconds: v.number(),
    server_typing_stopped_wait_period_milliseconds: v.number(),
    server_web_public_streams_enabled: v.boolean(),
    settings_send_digest_emails: v.boolean(),
    stop_words: v.array(v.string()),
    upgrade_text_for_wide_organization_logo: v.string(),
    zulip_feature_level: v.number(),
    zulip_merge_base: v.string(),
    zulip_plan_is_not_limited: v.boolean(),
    zulip_version: v.string(),
});

export const state_data_schema = v.intersect([
    v.pipe(
        v.object({alert_words: v.array(v.string())}),
        v.transform((alert_words) => ({alert_words})),
    ),
    v.pipe(
        v.object({realm_emoji: realm_emoji_map_schema}),
        v.transform((emoji) => ({emoji})),
    ),
    v.pipe(
        v.object({realm_bots: v.array(server_add_bot_schema)}),
        v.transform((bot) => ({bot})),
    ),
    v.pipe(
        v.object({
            realm_users: v.array(user_schema),
            realm_non_active_users: v.array(user_schema),
            cross_realm_bots: v.array(user_schema),
        }),
        v.transform((people) => ({people})),
    ),
    v.pipe(
        v.object({
            recent_private_conversations: v.array(
                v.object({
                    max_message_id: v.number(),
                    user_ids: v.array(v.number()),
                }),
            ),
        }),
        v.transform((pm_conversations) => ({pm_conversations})),
    ),
    v.pipe(
        v.object({
            presences: v.record(
                v.pipe(v.string(), v.transform(Number), v.number()),
                presence_schema,
            ),
            server_timestamp: v.number(),
            presence_last_update_id: v.optional(v.number()),
        }),
        v.transform((presence) => ({presence})),
    ),
    v.pipe(
        v.object({saved_snippets: v.array(saved_snippet_schema)}),
        v.transform((saved_snippets) => ({saved_snippets})),
    ),
    v.pipe(
        v.object({starred_messages: v.array(v.number())}),
        v.transform((starred_messages) => ({starred_messages})),
    ),
    v.pipe(
        v.object({
            subscriptions: v.array(api_stream_subscription_schema),
            unsubscribed: v.array(api_stream_subscription_schema),
            never_subscribed: v.array(never_subscribed_stream_schema),
            realm_default_streams: v.array(v.number()),
        }),
        v.transform((stream_data) => ({stream_data})),
    ),
    v.pipe(
        v.object({realm_user_groups: v.array(raw_user_group_schema)}),
        v.transform((user_groups) => ({user_groups})),
    ),
    v.pipe(
        v.object({
            unread_msgs: v.object({
                pms: v.array(unread_direct_message_info_schema),
                streams: v.array(unread_stream_info_schema),
                huddles: v.array(unread_direct_message_group_info_schema),
                mentions: v.array(v.number()),
                count: v.number(),
                old_unreads_missing: v.boolean(),
            }),
        }),
        v.transform((unread) => ({unread})),
    ),
    v.pipe(
        v.object({muted_users: v.array(muted_user_schema)}),
        v.transform((muted_users) => ({muted_users})),
    ),
    v.pipe(
        v.object({user_topics: v.array(user_topic_schema)}),
        v.transform((user_topics) => ({user_topics})),
    ),
    v.pipe(
        v.object({user_status: v.record(v.string(), user_status_schema)}),
        v.transform((user_status) => ({user_status})),
    ),
    v.pipe(
        v.object({user_settings: user_settings_schema}),
        v.transform((user_settings) => ({user_settings})),
    ),
    v.pipe(
        v.object({realm_user_settings_defaults: realm_default_settings_schema}),
        v.transform((realm_settings_defaults) => ({realm_settings_defaults})),
    ),
    v.pipe(
        v.object({scheduled_messages: v.array(scheduled_message_schema)}),
        v.transform((scheduled_messages) => ({scheduled_messages})),
    ),
    v.pipe(
        v.object({
            queue_id: NOT_TYPED_YET,
            server_generation: NOT_TYPED_YET,
            event_queue_longpoll_timeout_seconds: NOT_TYPED_YET,
            last_event_id: NOT_TYPED_YET,
        }),
        v.transform((server_events) => ({server_events})),
    ),
    v.pipe(
        v.object({max_message_id: v.number()}),
        v.transform((local_message) => ({local_message})),
    ),
    v.pipe(
        v.object({onboarding_steps: v.array(onboarding_step_schema)}),
        v.transform((onboarding_steps) => ({onboarding_steps})),
    ),
    v.pipe(
        current_user_schema,
        v.transform((current_user) => ({current_user})),
    ),
    v.pipe(
        realm_schema,
        v.transform((realm) => ({realm})),
    ),
]);

export type StateData = v.InferOutput<typeof state_data_schema>;

export type CurrentUser = StateData["current_user"];
export type Realm = StateData["realm"];

export let current_user: CurrentUser;
export let realm: Realm;

export function set_current_user(initial_current_user: CurrentUser): void {
    current_user = initial_current_user;
}

export function set_realm(initial_realm: Realm): void {
    realm = initial_realm;
}
