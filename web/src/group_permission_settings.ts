import type {InputPillRenderingDetails} from "./input_pill";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";
import type {GroupPermissionSetting} from "./types";
import * as user_groups from "./user_groups";
import type {UserGroup} from "./user_groups";

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
    unique_id: number | string;
    user?: InputPillRenderingDetails;
};

function get_user_from_user_system_group(group_id: number): people.User {
    const group = user_groups.get_user_group_from_id(group_id);
    const group_member_id = [...group.members][0];
    return people.get_by_user_id(group_member_id);
}

function is_user_system_group(group_id: number): boolean {
    const group = user_groups.get_user_group_from_id(group_id);
    if (group.is_system_group && group.name.startsWith("user:")) {
        return true;
    }
    return false;
}

export function get_user_system_group_name_from_user_id(user_id: number): string {
    return `user:${user_id}`;
}

function get_single_user_group_options(
    current_setting_value: number | undefined,
): UserGroupForDropdownListWidget[] {
    if (current_setting_value === undefined) {
        return [
            {
                name: "You",
                unique_id: get_user_system_group_name_from_user_id(people.my_current_user_id()),
            },
        ];
    }

    if (is_user_system_group(current_setting_value)) {
        const group_member = get_user_from_user_system_group(current_setting_value);
        const group_creator_option: UserGroupForDropdownListWidget = {
            name: group_member.full_name,
            unique_id: current_setting_value,
        };
        const opts = {
            deactivated: !people.is_person_active(group_member.user_id),
            display_value: group_member.full_name,
            has_image: true,
            img_src: people.small_avatar_url_for_person(group_member),
        };
        group_creator_option.user = opts;
        return [group_creator_option];
    }

    return [];
}

export function get_realm_user_groups_for_dropdown_list_widget(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
    target_group?: UserGroup,
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

    let system_user_groups: UserGroupForDropdownListWidget[] =
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

    if (setting_name === "can_manage_group") {
        let current_setting_value;
        if (target_group !== undefined) {
            current_setting_value = target_group.can_manage_group;
        }
        const single_user_group_options = get_single_user_group_options(current_setting_value);
        system_user_groups = [...system_user_groups, ...single_user_group_options];
    }

    if (require_system_group) {
        return system_user_groups;
    }

    const user_groups_excluding_system_groups: UserGroupForDropdownListWidget[] = user_groups
        .get_realm_user_groups()
        .filter((group) => {
            if (target_group !== undefined && group.id === target_group.id) {
                return false;
            }
            return true;
        })
        .map((group) => ({
            name: group.name,
            unique_id: group.id,
        }));

    if (target_group !== undefined) {
        const current_group_option = {name: "Members of this group", unique_id: target_group.id};
        user_groups_excluding_system_groups.unshift(current_group_option);
    } else if (setting_name === "can_manage_group") {
        // For can_manage_group, we show "Members of this group"
        // option in group creation form as well. This code will
        // be cleaned up when we add API support for having
        // "Members of this group" option in group creation form
        // for can_mention_group setting as well.
        const current_group_option = {name: "Members of this group", unique_id: "created_group"};
        user_groups_excluding_system_groups.unshift(current_group_option);
    }

    return [...system_user_groups, ...user_groups_excluding_system_groups];
}
