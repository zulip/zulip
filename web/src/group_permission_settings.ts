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
