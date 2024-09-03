import {z} from "zod";

import {server_add_bot_schema} from "./bot_types";
import {realm_default_settings_schema} from "./realm_user_settings_defaults";
import {
    never_subscribed_stream_schema,
    stream_schema,
    stream_subscription_schema,
} from "./stream_types";
import {user_settings_schema} from "./user_settings";
import {user_status_schema} from "./user_status_types";

const NOT_TYPED_YET = z.unknown();

const group_permission_setting_schema = z.object({
    require_system_group: z.boolean(),
    allow_internet_group: z.boolean(),
    allow_owners_group: z.boolean(),
    allow_nobody_group: z.boolean(),
    allow_everyone_group: z.boolean(),
    default_group_name: z.string(),
    id_field_name: z.string(),
    default_for_system_groups: z.nullable(z.string()),
    allowed_system_groups: z.array(z.string()),
});
export type GroupPermissionSetting = z.output<typeof group_permission_setting_schema>;

export const narrow_term_schema = z.object({
    negated: z.optional(z.boolean()),
    operator: z.string(),
    operand: z.string(),
});
export type NarrowTerm = z.output<typeof narrow_term_schema>;

export const custom_profile_field_schema = z.object({
    display_in_profile_summary: z.optional(z.boolean()),
    field_data: z.string(),
    hint: z.string(),
    id: z.number(),
    name: z.string(),
    order: z.number(),
    required: z.boolean(),
    type: z.number(),
});

export type CustomProfileField = z.output<typeof custom_profile_field_schema>;

export const scheduled_message_schema = z
    .object({
        scheduled_message_id: z.number(),
        content: z.string(),
        rendered_content: z.string(),
        scheduled_delivery_timestamp: z.number(),
        failed: z.boolean(),
    })
    .and(
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

export const profile_datum_schema = z.object({
    value: z.string(),
    rendered_value: z.string().nullish(),
});

export const user_schema = z
    .object({
        user_id: z.number(),
        delivery_email: z.string().nullable(),
        email: z.string(),
        full_name: z.string(),
        // used for caching result of remove_diacritics.
        name_with_diacritics_removed: z.string().optional(),
        date_joined: z.string(),
        is_active: z.boolean().optional(),
        is_owner: z.boolean(),
        is_admin: z.boolean(),
        is_guest: z.boolean(),
        is_moderator: z.boolean().optional(),
        is_billing_admin: z.boolean().optional(),
        role: z.number(),
        timezone: z.string().optional(),
        avatar_url: z.string().nullish(),
        avatar_version: z.number(),
        profile_data: z.record(z.coerce.number(), profile_datum_schema).optional(),
        // used for fake user objects.
        is_missing_server_data: z.optional(z.boolean()),
        // used for inaccessible user objects.
        is_inaccessible_user: z.optional(z.boolean()),
        is_system_bot: z.optional(z.literal(true)),
    })
    .and(
        z.discriminatedUnion("is_bot", [
            z.object({
                is_bot: z.literal(false),
                bot_type: z.null().optional(),
            }),
            z.object({
                is_bot: z.literal(true),
                bot_type: z.number(),
                bot_owner_id: z.number().nullable(),
            }),
        ]),
    );

export const server_emoji_schema = z.object({
    id: z.string(),
    author_id: z.number(),
    deactivated: z.boolean(),
    name: z.string(),
    source_url: z.string(),
    still_url: z.string().nullable(),

    // Added later in `settings_emoji.ts` when setting up the emoji settings.
    author: user_schema.nullish(),
});

export const realm_emoji_map_schema = z.record(server_emoji_schema);

export const user_group_schema = z.object({
    description: z.string(),
    id: z.number(),
    name: z.string(),
    members: z.array(z.number()),
    is_system_group: z.boolean(),
    direct_subgroup_ids: z.array(z.number()),
    can_manage_group: z.number(),
    can_mention_group: z.number(),
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
    active_timestamp: z.number().optional(),
    idle_timestamp: z.number().optional(),
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
    avatar_url: z.string().nullish(),
    avatar_url_medium: z.string().nullish(),
    can_create_private_streams: z.boolean(),
    can_create_public_streams: z.boolean(),
    can_create_streams: z.boolean(),
    can_create_web_public_streams: z.boolean(),
    can_invite_others_to_realm: z.boolean(),
    can_subscribe_other_users: z.boolean(),
    delivery_email: z.string(),
    email: z.string(),
    full_name: z.string(),
    has_zoom_token: z.boolean(),
    is_admin: z.boolean(),
    is_billing_admin: z.boolean(),
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

// Sync this with zerver.lib.events.do_events_register.
const realm_schema = z.object({
    custom_profile_fields: z.array(custom_profile_field_schema),
    custom_profile_field_types: custom_profile_field_types_schema,
    demo_organization_scheduled_deletion_date: z.optional(z.number()),
    giphy_api_key: z.string(),
    giphy_rating_options: z
        .record(z.object({id: z.number(), name: z.string()}))
        .and(z.object({disabled: z.object({id: z.number(), name: z.string()})})),
    max_avatar_file_size_mib: z.number(),
    max_file_upload_size_mib: z.number(),
    max_icon_file_size_mib: z.number(),
    max_logo_file_size_mib: z.number(),
    max_message_length: z.number(),
    max_stream_description_length: NOT_TYPED_YET,
    max_stream_name_length: NOT_TYPED_YET,
    max_topic_length: z.number(),
    password_min_guesses: NOT_TYPED_YET,
    password_min_length: NOT_TYPED_YET,
    realm_add_custom_emoji_policy: z.number(),
    realm_allow_edit_history: z.boolean(),
    realm_allow_message_editing: NOT_TYPED_YET,
    realm_authentication_methods: z.record(
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
        big_blue_button: z.optional(z.object({name: z.string(), id: z.number()})),
    }),
    realm_avatar_changes_disabled: z.boolean(),
    realm_bot_creation_policy: z.number(),
    realm_bot_domain: z.string(),
    realm_can_access_all_users_group: z.number(),
    realm_can_create_public_channel_group: z.number(),
    realm_can_create_private_channel_group: z.number(),
    realm_can_create_web_public_channel_group: z.number(),
    realm_can_delete_any_message_group: z.number(),
    realm_create_multiuse_invite_group: z.number(),
    realm_create_private_stream_policy: z.number(),
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
    realm_delete_own_message_policy: z.number(),
    realm_description: z.string(),
    realm_digest_emails_enabled: NOT_TYPED_YET,
    realm_digest_weekday: NOT_TYPED_YET,
    realm_direct_message_initiator_group: z.number(),
    realm_direct_message_permission_group: z.number(),
    realm_disallow_disposable_email_addresses: z.boolean(),
    realm_domains: z.array(
        z.object({
            domain: z.string(),
            allow_subdomains: z.boolean(),
        }),
    ),
    realm_edit_topic_policy: z.number(),
    realm_email_auth_enabled: NOT_TYPED_YET,
    realm_email_changes_disabled: z.boolean(),
    realm_emails_restricted_to_domains: z.boolean(),
    realm_embedded_bots: NOT_TYPED_YET,
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
            // We currently ignore the `config` field in these objects.
        }),
    ),
    realm_inline_image_preview: NOT_TYPED_YET,
    realm_inline_url_embed_preview: NOT_TYPED_YET,
    realm_invite_required: NOT_TYPED_YET,
    realm_invite_to_realm_policy: z.number(),
    realm_invite_to_stream_policy: z.number(),
    realm_is_zephyr_mirror_realm: z.boolean(),
    realm_jitsi_server_url: z.nullable(z.string()),
    realm_linkifiers: z.array(
        z.object({
            pattern: z.string(),
            url_template: z.string(),
            id: z.number(),
        }),
    ),
    realm_logo_source: z.string(),
    realm_logo_url: z.string(),
    realm_mandatory_topics: z.boolean(),
    realm_message_content_allowed_in_email_notifications: NOT_TYPED_YET,
    realm_message_content_edit_limit_seconds: z.number().nullable(),
    realm_message_content_delete_limit_seconds: z.number().nullable(),
    realm_message_retention_days: z.number(),
    realm_move_messages_between_streams_limit_seconds: z.number().nullable(),
    realm_move_messages_between_streams_policy: z.number(),
    realm_move_messages_within_stream_limit_seconds: z.number().nullable(),
    realm_name_changes_disabled: z.boolean(),
    realm_name: z.string(),
    realm_new_stream_announcements_stream_id: z.number(),
    realm_night_logo_source: z.string(),
    realm_night_logo_url: z.string(),
    realm_org_type: z.number(),
    realm_password_auth_enabled: NOT_TYPED_YET,
    realm_plan_type: z.number(),
    realm_playgrounds: z.array(
        z.object({
            id: z.number(),
            name: z.string(),
            pygments_language: z.string(),
            url_template: z.string(),
        }),
    ),
    realm_presence_disabled: z.boolean(),
    realm_push_notifications_enabled: z.boolean(),
    realm_push_notifications_enabled_end_timestamp: NOT_TYPED_YET,
    realm_require_unique_names: z.boolean(),
    realm_send_welcome_emails: NOT_TYPED_YET,
    realm_signup_announcements_stream_id: z.number(),
    realm_upload_quota_mib: z.nullable(z.number()),
    realm_url: z.string(),
    realm_user_group_edit_policy: z.number(),
    realm_video_chat_provider: z.number(),
    realm_waiting_period_threshold: z.number(),
    realm_want_advertise_in_communities_directory: NOT_TYPED_YET,
    realm_wildcard_mention_policy: z.number(),
    realm_zulip_update_announcements_stream_id: z.number(),
    server_avatar_changes_disabled: z.boolean(),
    server_emoji_data_url: NOT_TYPED_YET,
    server_inline_image_preview: NOT_TYPED_YET,
    server_inline_url_embed_preview: NOT_TYPED_YET,
    server_jitsi_server_url: z.nullable(z.string()),
    server_name_changes_disabled: z.boolean(),
    server_needs_upgrade: z.boolean(),
    server_presence_offline_threshold_seconds: z.number(),
    server_presence_ping_interval_seconds: z.number(),
    server_supported_permission_settings: z.object({
        realm: z.record(group_permission_setting_schema),
        stream: z.record(group_permission_setting_schema),
        group: z.record(group_permission_setting_schema),
    }),
    server_thumbnail_formats: z.array(thumbnail_format_schema),
    server_typing_started_expiry_period_milliseconds: z.number(),
    server_typing_started_wait_period_milliseconds: z.number(),
    server_typing_stopped_wait_period_milliseconds: z.number(),
    server_web_public_streams_enabled: z.boolean(),
    settings_send_digest_emails: NOT_TYPED_YET,
    stop_words: z.array(z.string()),
    upgrade_text_for_wide_organization_logo: NOT_TYPED_YET,
    zulip_feature_level: NOT_TYPED_YET,
    zulip_merge_base: z.string(),
    zulip_plan_is_not_limited: z.boolean(),
    zulip_version: z.string(),
});

export const state_data_schema = z
    .object({alert_words: z.array(z.string())})
    .transform((alert_words) => ({alert_words}))
    .and(z.object({realm_emoji: realm_emoji_map_schema}).transform((emoji) => ({emoji})))
    .and(z.object({realm_bots: z.array(server_add_bot_schema)}).transform((bot) => ({bot})))
    .and(
        z
            .object({
                realm_users: z.array(user_schema),
                realm_non_active_users: z.array(user_schema),
                cross_realm_bots: z.array(user_schema),
            })
            .transform((people) => ({people})),
    )
    .and(
        z
            .object({
                recent_private_conversations: z.array(
                    z.object({
                        max_message_id: z.number(),
                        user_ids: z.array(z.number()),
                    }),
                ),
            })
            .transform((pm_conversations) => ({pm_conversations})),
    )
    .and(
        z
            .object({
                presences: z.record(z.coerce.number(), presence_schema),
                server_timestamp: z.number(),
                presence_last_update_id: z.number().optional(),
            })
            .transform((presence) => ({presence})),
    )
    .and(
        z
            .object({starred_messages: z.array(z.number())})
            .transform((starred_messages) => ({starred_messages})),
    )
    .and(
        z
            .object({
                subscriptions: z.array(stream_subscription_schema),
                unsubscribed: z.array(stream_subscription_schema),
                never_subscribed: z.array(never_subscribed_stream_schema),
                realm_default_streams: z.array(stream_schema),
            })
            .transform((stream_data) => ({stream_data})),
    )
    .and(
        z
            .object({realm_user_groups: z.array(user_group_schema)})
            .transform((user_groups) => ({user_groups})),
    )
    .and(
        z
            .object({
                unread_msgs: z.object({
                    pms: z.array(unread_direct_message_info_schema),
                    streams: z.array(unread_stream_info_schema),
                    huddles: z.array(unread_direct_message_group_info_schema),
                    mentions: z.array(z.number()),
                    count: z.number(),
                    old_unreads_missing: z.boolean(),
                }),
            })
            .transform((unread) => ({unread})),
    )
    .and(
        z
            .object({muted_users: z.array(muted_user_schema)})
            .transform((muted_users) => ({muted_users})),
    )
    .and(
        z
            .object({user_topics: z.array(user_topic_schema)})
            .transform((user_topics) => ({user_topics})),
    )
    .and(
        z
            .object({user_status: z.record(user_status_schema)})
            .transform((user_status) => ({user_status})),
    )
    .and(
        z
            .object({user_settings: user_settings_schema})
            .transform((user_settings) => ({user_settings})),
    )
    .and(
        z
            .object({realm_user_settings_defaults: realm_default_settings_schema})
            .transform((realm_settings_defaults) => ({realm_settings_defaults})),
    )
    .and(
        z
            .object({scheduled_messages: z.array(scheduled_message_schema)})
            .transform((scheduled_messages) => ({scheduled_messages})),
    )
    .and(
        z
            .object({
                queue_id: NOT_TYPED_YET,
                server_generation: NOT_TYPED_YET,
                event_queue_longpoll_timeout_seconds: NOT_TYPED_YET,
                last_event_id: NOT_TYPED_YET,
            })
            .transform((server_events) => ({server_events})),
    )
    .and(z.object({max_message_id: z.number()}).transform((local_message) => ({local_message})))
    .and(
        z
            .object({onboarding_steps: z.array(onboarding_step_schema)})
            .transform((onboarding_steps) => ({onboarding_steps})),
    )
    .and(current_user_schema.transform((current_user) => ({current_user})))
    .and(realm_schema.transform((realm) => ({realm})));

export type StateData = z.infer<typeof state_data_schema>;

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
