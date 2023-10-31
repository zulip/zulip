import {page_params} from "./page_params";
import type {GroupPermissionSetting} from "./types";

export function get_group_permission_setting_config(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
): GroupPermissionSetting | undefined {
    const permission_settings_dict = page_params.server_supported_permission_settings;

    const permission_config_dict = permission_settings_dict[setting_type][setting_name];

    if (!permission_config_dict) {
        throw new Error(`Invalid setting: ${setting_name}`);
    }
    return permission_config_dict;
}
