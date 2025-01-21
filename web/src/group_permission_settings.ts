import {z} from "zod";

import {$t} from "./i18n.ts";
import {page_params} from "./page_params.ts";
import * as settings_config from "./settings_config.ts";
import {realm} from "./state_data.ts";
import type {GroupPermissionSetting, GroupSettingValue} from "./state_data.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";

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

export type StreamGroupSettingName =
    | "can_add_subscribers_group"
    | "can_administer_channel_group"
    | "can_remove_subscribers_group"
    | "can_send_message_group";

export function get_realm_user_groups_for_setting(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
    for_new_settings_ui = false,
): UserGroup[] {
    const group_setting_config = get_group_permission_setting_config(setting_name, setting_type);

    if (group_setting_config === undefined) {
        return [];
    }

    const system_user_groups = settings_config.system_user_groups_list
        .filter((group) =>
            user_groups.check_system_user_group_allowed_for_setting(
                group.name,
                group_setting_config,
                for_new_settings_ui,
            ),
        )
        .map((group) => {
            const user_group = user_groups.get_user_group_from_name(group.name);
            if (!user_group) {
                throw new Error(`Unknown group name: ${group.name}`);
            }
            return user_group;
        });

    if (!page_params.development_environment || group_setting_config.require_system_group) {
        return system_user_groups;
    }

    const user_groups_excluding_system_groups = user_groups.get_realm_user_groups();

    return [...system_user_groups, ...user_groups_excluding_system_groups];
}

export type UserGroupForDropdownListWidget = {
    name: string;
    unique_id: number;
};

export function get_realm_user_groups_for_dropdown_list_widget(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
): UserGroupForDropdownListWidget[] {
    const allowed_setting_groups = get_realm_user_groups_for_setting(setting_name, setting_type);

    return allowed_setting_groups.map((group) => {
        if (!group.is_system_group) {
            return {
                name: group.name,
                unique_id: group.id,
            };
        }

        const display_name = settings_config.system_user_groups_list.find(
            (system_group) => system_group.name === group.name,
        )!.dropdown_option_name;

        return {
            name: user_groups.get_display_name_for_system_group_option(setting_name, display_name),
            unique_id: group.id,
        };
    });
}

export type AssignedGroupPermission = {
    setting_name: RealmGroupSettingName | StreamGroupSettingName;
    can_edit: boolean;
    tooltip_message?: string;
};

export function get_assigned_permission_object(
    setting_value: GroupSettingValue,
    setting_name: RealmGroupSettingName | StreamGroupSettingName,
    group_id: number,
    can_edit_settings: boolean,
): AssignedGroupPermission | undefined {
    const assigned_permission_object: AssignedGroupPermission = {
        setting_name,
        can_edit: can_edit_settings,
    };

    if (!can_edit_settings) {
        assigned_permission_object.tooltip_message = $t({
            defaultMessage: "You are not allowed to remove this permission.",
        });
    }

    if (typeof setting_value === "number") {
        if (setting_value === group_id) {
            return assigned_permission_object;
        }

        if (user_groups.is_subgroup_of_target_group(setting_value, group_id)) {
            if (can_edit_settings) {
                assigned_permission_object.can_edit = false;
                const supergroup = user_groups.get_user_group_from_id(setting_value);
                assigned_permission_object.tooltip_message = $t(
                    {
                        defaultMessage:
                            "This group has this permission because it's a subgroup of {supergroup_name}.",
                    },
                    {
                        supergroup_name: user_groups.get_display_group_name(supergroup.name),
                    },
                );
            }
            return assigned_permission_object;
        }

        return undefined;
    }

    const direct_subgroup_ids = setting_value.direct_subgroups;
    if (direct_subgroup_ids.includes(group_id)) {
        return assigned_permission_object;
    }

    for (const direct_subgroup_id of direct_subgroup_ids) {
        if (user_groups.is_subgroup_of_target_group(direct_subgroup_id, group_id)) {
            if (can_edit_settings) {
                assigned_permission_object.can_edit = false;
                const supergroup = user_groups.get_user_group_from_id(direct_subgroup_id);
                assigned_permission_object.tooltip_message = $t(
                    {
                        defaultMessage:
                            "This group has this permission because it's a subgroup of {supergroup_name}.",
                    },
                    {
                        supergroup_name: user_groups.get_display_group_name(supergroup.name),
                    },
                );
            }
            return assigned_permission_object;
        }
    }

    return undefined;
}
