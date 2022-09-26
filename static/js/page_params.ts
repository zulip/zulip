import $ from "jquery";

const t1 = performance.now();
export const page_params: {
    language_list: {
        code: string;
        locale: string;
        name: string;
        percent_translated: number | undefined;
    }[];
    development_environment: boolean;
    is_admin: boolean;
    is_guest: boolean;
    is_moderator: boolean;
    is_owner: boolean;
    is_spectator: boolean;
    realm_add_custom_emoji_policy: number;
    realm_avatar_changes_disabled: boolean;
    realm_create_private_stream_policy: number;
    realm_create_public_stream_policy: number;
    realm_create_web_public_stream_policy: number;
    realm_delete_own_message_policy: number;
    realm_edit_topic_policy: number;
    realm_email_address_visibility: number;
    realm_enable_spectator_access: boolean;
    realm_invite_to_realm_policy: number;
    realm_invite_to_stream_policy: number;
    realm_move_messages_between_streams_policy: number;
    realm_name_changes_disabled: boolean;
    realm_push_notifications_enabled: boolean;
    realm_user_group_edit_policy: number;
    realm_waiting_period_threshold: number;
    request_language: string;
    server_avatar_changes_disabled: boolean;
    server_name_changes_disabled: boolean;
    server_web_public_streams_enabled: boolean;
    translation_data: Record<string, string>;
    zulip_plan_is_not_limited: boolean;
} = $("#page-params").remove().data("params");
const t2 = performance.now();
export const page_params_parse_time = t2 - t1;
if (!page_params) {
    throw new Error("Missing page-params");
}
