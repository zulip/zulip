import * as z from "zod/mini";

import {attachment_schema} from "./attachments.ts";
import {server_add_bot_schema, server_update_bot_schema} from "./bot_types.ts";
import {presence_info_from_event_schema} from "./presence.ts";
import {realm_default_settings_schema} from "./realm_user_settings_defaults.ts";
import {server_message_schema} from "./server_message.ts";
import {export_consent_schema, realm_export_schema} from "./settings_exports.ts";
import {user_settings_property_schema} from "./settings_preferences.ts";
import {
    channel_folder_schema,
    custom_profile_field_schema,
    muted_user_schema,
    onboarding_step_schema,
    raw_user_group_schema,
    realm_domain_schema,
    realm_emoji_map_schema,
    realm_linkifier_schema,
    realm_playground_schema,
    reminder_schema,
    saved_snippet_schema,
    scheduled_message_schema,
    user_schema,
    user_topic_schema,
} from "./state_data.ts";
import {
    api_stream_schema,
    api_stream_subscription_schema,
    updatable_stream_properties_schema,
} from "./stream_types.ts";
import {anonymous_group_schema, group_setting_value_schema, topic_link_schema} from "./types.ts";
import {typing_event_schema} from "./typing_events.ts";
import {user_update_schema} from "./user_events.ts";
import {user_status_schema} from "./user_status_types.ts";

const stream_group_schema = z.object({
    name: z.string(),
    id: z.number(),
    description: z.string(),
    streams: z.array(z.number()),
});

const draft_schema = z.object({
    id: z.number(),
    type: z.enum(["", "stream", "private"]),
    to: z.array(z.number()),
    topic: z.string(),
    content: z.string(),
    timestamp: z.optional(z.number()),
});

const muted_topic_schema = z.tuple([z.string(), z.string(), z.number()]);

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

export const base_server_event_schema = z.catchall(
    z.object({id: z.number(), type: z.string(), op: z.optional(z.string())}),
    z.unknown(),
);

export type BaseServerEvent = z.output<typeof base_server_event_schema>;

const server_event_union = z.discriminatedUnion("type", [
    z.object({type: z.literal("alert_words"), alert_words: z.array(z.string())}),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("attachment"),
            op: z.literal("add"),
            attachment: attachment_schema,
            upload_space_used: z.number(),
        }),
        z.object({
            type: z.literal("attachment"),
            op: z.literal("remove"),
            attachment: z.object({id: z.number()}),
            upload_space_used: z.number(),
        }),
        z.object({
            type: z.literal("attachment"),
            op: z.literal("update"),
            attachment: attachment_schema,
            upload_space_used: z.number(),
        }),
    ]),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("channel_folder"),
            op: z.literal("add"),
            channel_folder: channel_folder_schema,
        }),
        z.object({
            type: z.literal("channel_folder"),
            op: z.literal("reorder"),
            order: z.array(z.number()),
        }),
        channel_folder_update_event_schema,
    ]),
    z.object({
        type: z.literal("custom_profile_fields"),
        fields: z.array(custom_profile_field_schema),
    }),
    z.object({
        type: z.literal("default_stream_groups"),
        default_stream_groups: z.array(stream_group_schema),
    }),
    z.object({type: z.literal("default_streams"), default_streams: z.array(z.number())}),
    z.discriminatedUnion("message_type", [
        z.object({
            type: z.literal("delete_message"),
            message_type: z.literal("private"),
            message_ids: z.array(z.number()),
        }),
        z.object({
            type: z.literal("delete_message"),
            message_type: z.literal("stream"),
            message_ids: z.array(z.number()),
            stream_id: z.number(),
            topic: z.string(),
        }),
    ]),
    z.discriminatedUnion("op", [
        z.object({type: z.literal("drafts"), op: z.literal("add"), drafts: z.array(draft_schema)}),
        z.object({type: z.literal("drafts"), op: z.literal("update"), draft: draft_schema}),
        z.object({type: z.literal("drafts"), op: z.literal("remove"), draft_id: z.number()}),
    ]),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("saved_snippets"),
            op: z.literal("add"),
            saved_snippet: saved_snippet_schema,
        }),
        z.object({
            type: z.literal("saved_snippets"),
            op: z.literal("update"),
            saved_snippet: saved_snippet_schema,
        }),
        z.object({
            type: z.literal("saved_snippets"),
            op: z.literal("remove"),
            saved_snippet_id: z.number(),
        }),
    ]),
    z.object({type: z.literal("has_zoom_token"), value: z.boolean()}),
    z.object({type: z.literal("heartbeat")}),
    z.object({type: z.literal("invites_changed")}),
    z.object({
        type: z.literal("message"),
        flags: z.array(z.string()),
        message: server_message_schema,
        local_message_id: z.optional(z.string()),
    }),
    z.object({type: z.literal("muted_topics"), muted_topics: z.array(muted_topic_schema)}),
    z.object({type: z.literal("muted_users"), muted_users: z.array(muted_user_schema)}),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("navigation_view"),
            op: z.literal("add"),
            navigation_view: z.object({
                fragment: z.string(),
                is_pinned: z.boolean(),
                name: z.nullable(z.string()),
            }),
        }),
        z.object({
            type: z.literal("navigation_view"),
            op: z.literal("remove"),
            fragment: z.string(),
        }),
        z.object({
            type: z.literal("navigation_view"),
            op: z.literal("update"),
            fragment: z.string(),
            data: z.object({is_pinned: z.optional(z.boolean()), name: z.optional(z.string())}),
        }),
    ]),
    z.object({
        type: z.literal("onboarding_steps"),
        onboarding_steps: z.array(onboarding_step_schema),
    }),
    // Legacy format because we don't enable simplified_presence_events
    z.object({
        type: z.literal("presence"),
        user_id: z.number(),
        server_timestamp: z.number(),
        presence: presence_info_from_event_schema,
        email: z.optional(z.string()),
    }),
    z.object({
        type: z.literal("push_device"),
        push_account_id: z.string(),
        status: z.enum(["active", "failed", "pending"]),
        error_code: z.optional(z.string()),
    }),
    z.object({
        type: z.literal("reaction"),
        op: z.enum(["add", "remove"]),
        message_id: z.number(),
        emoji_name: z.string(),
        emoji_code: z.string(),
        reaction_type: z.enum(["unicode_emoji", "realm_emoji", "zulip_extra_emoji"]),
        user_id: z.number(),
    }),
    z.discriminatedUnion("op", [
        z.object({type: z.literal("realm"), op: z.literal("deactivated"), realm_id: z.number()}),
        z.object({
            type: z.literal("realm"),
            op: z.literal("update"),
            property: z.string(),
            value: z.union([z.boolean(), z.number(), z.string(), z.null()]), // TODO/typescript: be specific depending on property
        }),
        z.discriminatedUnion("property", [
            z.object({
                type: z.literal("realm"),
                op: z.literal("update_dict"),
                property: z.literal("default"),
                data: z.union([
                    z.object({allow_message_editing: z.boolean()}),
                    z.object({
                        authentication_methods: z.record(
                            z.string(),
                            z.object({
                                enabled: z.boolean(),
                                available: z.boolean(),
                                unavailable_reason: z.optional(z.string()),
                            }),
                        ),
                    }),
                    z.object({allow_message_editing: z.boolean()}),
                    z.object({message_content_edit_limit_seconds: z.optional(z.number())}),
                    z.partialRecord(
                        z.enum([
                            "create_multiuse_invite_group",
                            "can_access_all_users_group",
                            "can_add_custom_emoji_group",
                            "can_add_subscribers_group",
                            "can_create_bots_group",
                            "can_create_groups",
                            "can_create_public_channel_group",
                            "can_create_private_channel_group",
                            "can_create_web_public_channel_group",
                            "can_create_write_only_bots_group",
                            "can_delete_any_message_group",
                            "can_delete_own_message_group",
                            "can_invite_users_group",
                            "can_manage_all_groups",
                            "can_manage_billing_group",
                            "can_mention_many_users_group",
                            "can_move_messages_between_channels_group",
                            "can_move_messages_between_topics_group",
                            "can_resolve_topics_group",
                            "can_set_delete_message_policy_group",
                            "can_set_topics_policy_group",
                            "can_summarize_topics_group",
                            "direct_message_initiator_group",
                            "direct_message_permission_group",
                        ]),
                        group_setting_value_schema,
                    ),
                    z.object({
                        plan_type: z.number(),
                        upload_quota_mib: z.optional(z.number()),
                        max_file_upload_size_mib: z.number(),
                    }),
                    z.object({topics_policy: z.string(), mandatory_topics: z.boolean()}),
                ]),
            }),
            z.object({
                type: z.literal("realm"),
                op: z.literal("update_dict"),
                property: z.literal("icon"),
                data: z.object({icon_url: z.string(), icon_source: z.string()}),
            }),
            z.object({
                type: z.literal("realm"),
                op: z.literal("update_dict"),
                property: z.literal("logo"),
                data: z.object({logo_url: z.string(), logo_source: z.string()}),
            }),
            z.object({
                type: z.literal("realm"),
                op: z.literal("update_dict"),
                property: z.literal("night_logo"),
                data: z.object({night_logo_url: z.string(), night_logo_source: z.string()}),
            }),
        ]),
    ]),
    z.discriminatedUnion("op", [
        z.object({type: z.literal("realm_bot"), op: z.literal("add"), bot: server_add_bot_schema}),
        z.object({
            type: z.literal("realm_bot"),
            op: z.literal("delete"),
            bot: z.object({user_id: z.number()}),
        }),
        z.object({
            type: z.literal("realm_bot"),
            op: z.literal("update"),
            bot: server_update_bot_schema,
        }),
    ]),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("realm_domains"),
            op: z.literal("add"),
            realm_domain: realm_domain_schema,
        }),
        z.object({
            type: z.literal("realm_domains"),
            op: z.literal("change"),
            realm_domain: realm_domain_schema,
        }),
        z.object({type: z.literal("realm_domains"), op: z.literal("remove"), domain: z.string()}),
    ]),
    z.object({
        type: z.literal("realm_playgrounds"),
        realm_playgrounds: z.array(realm_playground_schema),
    }),
    z.object({
        type: z.literal("realm_emoji"),
        op: z.literal("update"),
        realm_emoji: realm_emoji_map_schema,
    }),
    z.object({type: z.literal("realm_export"), exports: z.array(realm_export_schema)}),
    z.object({type: z.literal("realm_export_consent"), ...export_consent_schema.shape}),
    z.object({
        type: z.literal("realm_linkifiers"),
        realm_linkifiers: z.array(realm_linkifier_schema),
    }),
    z.object({
        type: z.literal("realm_user_settings_defaults"),
        op: z.literal("update"),
        property: z.keyof(realm_default_settings_schema),
        value: z.union([z.boolean(), z.number(), z.string()]), // TODO/typescript: be specific depending on property
    }),
    z.discriminatedUnion("op", [
        z.object({type: z.literal("realm_user"), op: z.literal("add"), person: user_schema}),
        z.object({
            type: z.literal("realm_user"),
            op: z.literal("update"),
            person: user_update_schema,
        }),
        z.object({
            type: z.literal("realm_user"),
            op: z.literal("remove"),
            person: z.object({user_id: z.number(), full_name: z.string()}),
        }),
    ]),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("reminders"),
            op: z.literal("add"),
            reminders: z.array(reminder_schema),
        }),
        z.object({type: z.literal("reminders"), op: z.literal("remove"), reminder_id: z.number()}),
    ]),
    z.object({
        type: z.literal("restart"),
        zulip_version: z.string(),
        zulip_merge_base: z.string(),
        zulip_feature_level: z.number(),
        server_generation: z.number(),
    }),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("scheduled_messages"),
            op: z.literal("add"),
            scheduled_messages: z.array(scheduled_message_schema),
        }),
        z.object({
            type: z.literal("scheduled_messages"),
            op: z.literal("update"),
            scheduled_message: scheduled_message_schema,
        }),
        z.object({
            type: z.literal("scheduled_messages"),
            op: z.literal("remove"),
            scheduled_message_id: z.number(),
        }),
    ]),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("stream"),
            op: z.literal("create"),
            streams: z.array(api_stream_schema),
        }),
        z.object({
            type: z.literal("stream"),
            op: z.literal("delete"),
            streams: z.array(z.object({stream_id: z.number()})),
            stream_ids: z.array(z.number()),
        }),
        z.object({
            type: z.literal("stream"),
            op: z.literal("update"),
            property: z.keyof(updatable_stream_properties_schema),
            value: z.union([z.boolean(), z.number(), z.string(), anonymous_group_schema, z.null()]), // TODO/typescript: be specific depending on property
            name: z.string(),
            stream_id: z.number(),
            rendered_description: z.optional(z.string()),
            history_public_to_subscribers: z.optional(z.boolean()),
            is_web_public: z.optional(z.boolean()),
        }),
    ]),
    z.object({
        type: z.literal("submessage"),
        message_id: z.number(),
        submessage_id: z.number(),
        sender_id: z.number(),
        msg_type: z.string(),
        content: z.string(),
    }),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("subscription"),
            op: z.literal("add"),
            subscriptions: z.array(api_stream_subscription_schema),
        }),
        z.object({
            type: z.literal("subscription"),
            op: z.literal("peer_add"),
            user_ids: z.array(z.number()),
            stream_ids: z.array(z.number()),
        }),
        z.object({
            type: z.literal("subscription"),
            op: z.literal("peer_remove"),
            user_ids: z.array(z.number()),
            stream_ids: z.array(z.number()),
        }),
        z.object({
            type: z.literal("subscription"),
            op: z.literal("remove"),
            subscriptions: z.array(z.object({name: z.string(), stream_id: z.number()})),
        }),
        z.object({
            type: z.literal("subscription"),
            op: z.literal("update"),
            property: z.keyof(updatable_stream_properties_schema),
            stream_id: z.number(),
            value: z.union([z.boolean(), z.number(), z.string()]), // TODO/typescript: be specific depending on property
        }),
    ]),
    z.pipe(z.looseObject({type: z.literal("typing")}), typing_event_schema),
    z.object({
        type: z.literal("typing_edit_message"),
        op: z.enum(["start", "stop"]),
        sender_id: z.number(),
        message_id: z.number(),
        recipient: z.discriminatedUnion("type", [
            z.object({type: z.literal("channel"), channel_id: z.number(), topic: z.string()}),
            z.object({type: z.literal("direct"), user_ids: z.array(z.number())}),
        ]),
    }),
    // We do not receive type="update_display_settings" due to
    // user_settings_object capability
    // We do not receive type="update_global_notifications" due to
    // user_settings_object capability
    z.object({
        type: z.literal("user_settings"),
        op: z.literal("update"),
        property: user_settings_property_schema,
        value: z.union([z.boolean(), z.number(), z.string()]), // TODO/typescript: be specific depending on property
        language_name: z.optional(z.string()),
    }),
    z.object({type: z.literal("user_topic"), ...user_topic_schema.shape}),
    update_message_event_schema,
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("update_message_flags"),
            op: z.literal("add"),
            operation: z.literal("add"),
            flag: z.string(),
            messages: z.array(z.number()),
            all: z.boolean(),
        }),
        z.object({
            type: z.literal("update_message_flags"),
            op: z.literal("remove"),
            operation: z.literal("remove"),
            flag: z.string(),
            messages: z.array(z.number()),
            all: z.boolean(),
            message_details: z.optional(message_details_schema),
        }),
    ]),
    z.discriminatedUnion("op", [
        z.object({
            type: z.literal("user_group"),
            op: z.literal("add"),
            group: raw_user_group_schema,
        }),
        z.object({
            type: z.literal("user_group"),
            op: z.literal("add_members"),
            group_id: z.number(),
            user_ids: z.array(z.number()),
        }),
        // We do not receive op="remove" due to include_deactivated_groups
        // capability
        z.object({
            type: z.literal("user_group"),
            op: z.literal("remove_members"),
            group_id: z.number(),
            user_ids: z.array(z.number()),
        }),
        user_group_update_event_schema,
        z.object({
            type: z.literal("user_group"),
            op: z.literal("add_subgroups"),
            group_id: z.number(),
            direct_subgroup_ids: z.array(z.number()),
        }),
        z.object({
            type: z.literal("user_group"),
            op: z.literal("remove_subgroups"),
            group_id: z.number(),
            direct_subgroup_ids: z.array(z.number()),
        }),
    ]),
    z.pipe(
        z.looseObject({type: z.literal("user_status"), user_id: z.number()}),
        z.intersection(
            z.object({type: z.literal("user_status"), user_id: z.number()}),
            user_status_schema,
        ),
    ),
    z.object({type: z.literal("web_reload_client"), immediate: z.boolean()}),
]);

export const server_event_schema = z.intersection(z.object({id: z.number()}), server_event_union);

export type ServerEvent = z.output<typeof server_event_schema>;
