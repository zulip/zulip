import {z} from "zod";

import {realm} from "./state_data.ts";
import type {GroupPermissionSetting} from "./state_data.ts";

export function get_group_permission_setting_config(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
): GroupPermissionSetting | undefined {
    const permission_settings_dict = realm.server_supported_permission_settings;

    const permission_config_dict = permission_settings_dict[setting_type][setting_name];

    if (!permission_config_dict) {
        throw new Error(`Invalid setting: ${setting_name}`);
    }
    return permission_config_dict;
}

export const group_setting_name_schema = z.enum([
    "can_add_members_group",
    "can_join_group",
    "can_leave_group",
    "can_manage_group",
    "can_mention_group",
    "can_remove_members_group",
]);

export type GroupSettingName = z.infer<typeof group_setting_name_schema>;

export function get_group_permission_settings(): GroupSettingName[] {
    return z
        .array(group_setting_name_schema)
        .parse(Object.keys(realm.server_supported_permission_settings.group));
}

export const realm_group_setting_name_schema = z.enum([
    "can_access_all_users_group",
    "can_add_custom_emoji_group",
    "can_add_subscribers_group",
    "can_create_groups",
    "can_create_public_channel_group",
    "can_create_private_channel_group",
    "can_create_web_public_channel_group",
    "can_delete_any_message_group",
    "can_delete_own_message_group",
    "can_invite_users_group",
    "can_manage_all_groups",
    "can_move_messages_between_channels_group",
    "can_move_messages_between_topics_group",
    "create_multiuse_invite_group",
    "direct_message_initiator_group",
    "direct_message_permission_group",
]);
export type RealmGroupSettingName = z.infer<typeof realm_group_setting_name_schema>;
