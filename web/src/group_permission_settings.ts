import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import type {GroupPermissionSetting} from "./types";
import * as user_groups from "./user_groups";

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

type UserGroupForDropdownListWidget = {
    name: string;
    unique_id: number;
};

export function get_realm_user_groups_for_dropdown_list_widget(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
): UserGroupForDropdownListWidget[] {
    const group_setting_config = get_group_permission_setting_config(setting_name, setting_type);

    if (group_setting_config === undefined) {
        return [];
    }

    const {
        require_system_group,
        allow_internet_group,
        allow_owners_group,
        allow_nobody_group,
        allow_everyone_group,
        allowed_system_groups,
    } = group_setting_config;

    const system_user_groups: UserGroupForDropdownListWidget[] =
        settings_config.system_user_groups_list
            .filter((group) => {
                if (!allow_internet_group && group.name === "role:internet") {
                    return false;
                }

                if (!allow_owners_group && group.name === "role:owners") {
                    return false;
                }

                if (!allow_nobody_group && group.name === "role:nobody") {
                    return false;
                }

                if (!allow_everyone_group && group.name === "role:everyone") {
                    return false;
                }

                if (allowed_system_groups.length && !allowed_system_groups.includes(group.name)) {
                    return false;
                }

                return true;
            })
            .map((group) => {
                const user_group = user_groups.get_user_group_from_name(group.name);
                if (!user_group) {
                    throw new Error(`Unknown group name: ${group.name}`);
                }
                return {
                    name: group.display_name,
                    unique_id: user_group.id,
                };
            });

    if (require_system_group) {
        return system_user_groups;
    }

    const user_groups_excluding_system_groups = user_groups
        .get_realm_user_groups()
        .map((group) => ({
            name: group.name,
            unique_id: group.id,
        }));

    return [...system_user_groups, ...user_groups_excluding_system_groups];
}
