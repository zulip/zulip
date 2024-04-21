import {z} from "zod";

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
// Sync this with zerver.lib.events.do_events_register.

const placement_schema = z.enum([
    "top",
    "left",
    "right",
    "bottom",
    "left_bottom",
    "viewport_center",
]);

export type Placement = z.infer<typeof placement_schema>;

const hotspot_location_schema = z.object({
    element: z.string(),
    offset_x: z.number(),
    offset_y: z.number(),
    popover: z.optional(placement_schema),
});

export type HotspotLocation = z.output<typeof hotspot_location_schema>;

const raw_hotspot_schema = z.object({
    delay: z.number(),
    description: z.string(),
    has_trigger: z.boolean(),
    name: z.string(),
    title: z.string(),
    type: z.literal("hotspot"),
});

export type RawHotspot = z.output<typeof raw_hotspot_schema>;

const hotspot_schema = raw_hotspot_schema.extend({
    location: hotspot_location_schema,
});

export type Hotspot = z.output<typeof hotspot_schema>;

const one_time_notice_schema = z.object({
    name: z.string(),
    type: z.literal("one_time_notice"),
});

const onboarding_step_schema = z.union([one_time_notice_schema, raw_hotspot_schema]);

export type OnboardingStep = z.output<typeof onboarding_step_schema>;

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

export const current_user_schema = z.object({
    avatar_source: z.string(),
    delivery_email: z.string(),
    is_admin: z.boolean(),
    is_billing_admin: z.boolean(),
    is_guest: z.boolean(),
    is_moderator: z.boolean(),
    is_owner: z.boolean(),
    onboarding_steps: z.array(onboarding_step_schema),
    user_id: z.number(),
});
// Sync this with zerver.lib.events.do_events_register.

export const realm_schema = z.object({
    custom_profile_fields: z.array(custom_profile_field_schema),
    custom_profile_field_types: z.object({
        SHORT_TEXT: z.object({id: z.number(), name: z.string()}),
        LONG_TEXT: z.object({id: z.number(), name: z.string()}),
        DATE: z.object({id: z.number(), name: z.string()}),
        SELECT: z.object({id: z.number(), name: z.string()}),
        URL: z.object({id: z.number(), name: z.string()}),
        EXTERNAL_ACCOUNT: z.object({id: z.number(), name: z.string()}),
        USER: z.object({id: z.number(), name: z.string()}),
        PRONOUNS: z.object({id: z.number(), name: z.string()}),
    }),
    max_avatar_file_size_mib: z.number(),
    max_icon_file_size_mib: z.number(),
    max_logo_file_size_mib: z.number(),
    max_message_length: z.number(),
    max_topic_length: z.number(),
    realm_add_custom_emoji_policy: z.number(),
    realm_allow_edit_history: z.boolean(),
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
    realm_bot_domain: z.string(),
    realm_can_access_all_users_group: z.number(),
    realm_create_multiuse_invite_group: z.number(),
    realm_create_private_stream_policy: z.number(),
    realm_create_public_stream_policy: z.number(),
    realm_create_web_public_stream_policy: z.number(),
    realm_default_code_block_language: z.string(),
    realm_default_language: z.string(),
    realm_delete_own_message_policy: z.number(),
    realm_description: z.string(),
    realm_disallow_disposable_email_addresses: z.boolean(),
    realm_domains: z.array(
        z.object({
            domain: z.string(),
            allow_subdomains: z.boolean(),
        }),
    ),
    realm_edit_topic_policy: z.number(),
    realm_email_changes_disabled: z.boolean(),
    realm_emails_restricted_to_domains: z.boolean(),
    realm_enable_guest_user_indicator: z.boolean(),
    realm_enable_spectator_access: z.boolean(),
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
    realm_private_message_policy: z.number(),
    realm_push_notifications_enabled: z.boolean(),
    realm_require_unique_names: z.boolean(),
    realm_signup_announcements_stream_id: z.number(),
    realm_upload_quota_mib: z.nullable(z.number()),
    realm_uri: z.string(),
    realm_user_group_edit_policy: z.number(),
    realm_video_chat_provider: z.number(),
    realm_waiting_period_threshold: z.number(),
    realm_wildcard_mention_policy: z.number(),
    realm_zulip_update_announcements_stream_id: z.number(),
    server_avatar_changes_disabled: z.boolean(),
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
    server_typing_started_expiry_period_milliseconds: z.number(),
    server_typing_started_wait_period_milliseconds: z.number(),
    server_typing_stopped_wait_period_milliseconds: z.number(),
    server_web_public_streams_enabled: z.boolean(),
    stop_words: z.array(z.string()),
    zulip_merge_base: z.string(),
    zulip_plan_is_not_limited: z.boolean(),
    zulip_version: z.string(),
});

export const state_data_schema = current_user_schema
    .merge(realm_schema)
    // TODO/typescript: Remove .passthrough() when all consumers have been
    // converted to TypeScript and the schema is complete.
    .passthrough();

export let current_user: z.infer<typeof current_user_schema>;
export let realm: z.infer<typeof realm_schema>;

export function set_current_user(initial_current_user: z.infer<typeof current_user_schema>): void {
    current_user = initial_current_user;
}

export function set_realm(initial_realm: z.infer<typeof realm_schema>): void {
    realm = initial_realm;
}
