import assert from "minimalistic-assert";
import {z} from "zod";

import * as blueslip from "./blueslip.ts";
import type * as dropdown_widget from "./dropdown_widget.ts";
import {$t} from "./i18n.ts";
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

export const group_group_setting_name_schema = z.enum([
    "can_add_members_group",
    "can_join_group",
    "can_leave_group",
    "can_manage_group",
    "can_mention_group",
    "can_remove_members_group",
]);

export type GroupGroupSettingName = z.infer<typeof group_group_setting_name_schema>;

export function get_group_permission_settings(): GroupGroupSettingName[] {
    return z
        .array(group_group_setting_name_schema)
        .parse(Object.keys(realm.server_supported_permission_settings.group));
}

export const realm_group_setting_name_schema = z.enum([
    "can_access_all_users_group",
    "can_add_custom_emoji_group",
    "can_add_subscribers_group",
    "can_create_groups",
    "can_create_bots_group",
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
    "can_set_topics_policy_group",
    "can_summarize_topics_group",
    "create_multiuse_invite_group",
    "direct_message_initiator_group",
    "direct_message_permission_group",
]);
export type RealmGroupSettingName = z.infer<typeof realm_group_setting_name_schema>;

export const stream_group_setting_name_schema = z.enum([
    "can_add_subscribers_group",
    "can_administer_channel_group",
    "can_move_messages_out_of_channel_group",
    "can_move_messages_within_channel_group",
    "can_remove_subscribers_group",
    "can_send_message_group",
    "can_subscribe_group",
]);
export type StreamGroupSettingName = z.infer<typeof stream_group_setting_name_schema>;

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

    if (group_setting_config.require_system_group) {
        return system_user_groups;
    }

    const user_groups_excluding_system_groups = user_groups.get_realm_user_groups();

    return [...system_user_groups, ...user_groups_excluding_system_groups];
}

export function get_realm_user_groups_for_dropdown_list_widget(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
): dropdown_widget.Option[] {
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
            name: display_name,
            unique_id: group.id,
        };
    });
}

export type AssignedGroupPermission = {
    setting_name: RealmGroupSettingName | StreamGroupSettingName | GroupGroupSettingName;
    can_edit: boolean;
    tooltip_message?: string;
};

export function get_tooltip_for_group_without_direct_permission(supergroup_id: number): string {
    const supergroup = user_groups.get_user_group_from_id(supergroup_id);
    return $t(
        {
            defaultMessage:
                "This group has this permission because it's a subgroup of {supergroup_name}.",
        },
        {
            supergroup_name: user_groups.get_display_group_name(supergroup.name),
        },
    );
}

export function get_assigned_permission_object(
    setting_value: GroupSettingValue,
    setting_name: RealmGroupSettingName | StreamGroupSettingName | GroupGroupSettingName,
    group_id: number,
    can_edit_settings: boolean,
    setting_type: "realm" | "stream" | "group",
): AssignedGroupPermission | undefined {
    // This function returns an object of type AssignedGroupPermission
    // containing details about whether the user can edit the setting,
    // if the group has the permission, and returns undefined otherwise.
    const assigned_permission_object: AssignedGroupPermission = {
        setting_name,
        can_edit: can_edit_settings,
    };

    if (!can_edit_settings) {
        if (!user_groups.group_has_permission(setting_value, group_id)) {
            // The group does not have permission.
            return undefined;
        }

        // Since user cannot change this setting, the tooltip is
        // the same whether the group has direct permission or has
        // permission due to being subgroup of a group with permission.
        assigned_permission_object.tooltip_message = $t({
            defaultMessage: "You are not allowed to remove this permission.",
        });
        return assigned_permission_object;
    }

    // The user has permission to change the setting, but whether the user
    // will be able to remove the permission for this particular group
    // depends on whether the group has the permission directly or not.
    if (typeof setting_value === "number") {
        if (setting_value === group_id) {
            // The group has permission directly, so the user can remove
            // the permission for this particular group, and there is no
            // need to show a tooltip.
            const permission_config = get_group_permission_setting_config(
                setting_name,
                setting_type,
            );
            assert(permission_config !== undefined);
            if (!permission_config.allow_nobody_group) {
                assigned_permission_object.can_edit = false;
                assigned_permission_object.tooltip_message = $t({
                    defaultMessage:
                        "This permission cannot be removed, as it would mean that nobody is allowed to take this action.",
                });
            }
            return assigned_permission_object;
        }

        if (user_groups.is_subgroup_of_target_group(setting_value, group_id)) {
            // The group has permission because it is one of the subgroups of
            // the group that has permission. Therefore, the user cannot remove
            // the permission for this group, and the UI should show a disabled
            // checkbox with an appropriate tooltip.
            assigned_permission_object.can_edit = false;
            assigned_permission_object.tooltip_message =
                get_tooltip_for_group_without_direct_permission(setting_value);
            return assigned_permission_object;
        }

        // The group does not have permission.
        return undefined;
    }

    // Setting is set to an anonymous group.
    const direct_subgroup_ids = setting_value.direct_subgroups;
    if (direct_subgroup_ids.includes(group_id)) {
        // The group is one of the groups that has permission and can be
        // changed to not have permission.
        if (
            setting_value.direct_subgroups.length === 1 &&
            setting_value.direct_members.length === 0
        ) {
            const permission_config = get_group_permission_setting_config(
                setting_name,
                setting_type,
            );
            assert(permission_config !== undefined);
            if (!permission_config.allow_nobody_group) {
                assigned_permission_object.can_edit = false;
                assigned_permission_object.tooltip_message = $t({
                    defaultMessage:
                        "This permission cannot be removed, as it would mean that nobody is allowed to take this action.",
                });
            }
        }
        return assigned_permission_object;
    }

    for (const direct_subgroup_id of direct_subgroup_ids) {
        if (user_groups.is_subgroup_of_target_group(direct_subgroup_id, group_id)) {
            // The group has permission because it is a subgroup of one of the
            // groups that has permission. Therefore, the user cannot remove the
            // permission for this group.
            assigned_permission_object.can_edit = false;
            assigned_permission_object.tooltip_message =
                get_tooltip_for_group_without_direct_permission(direct_subgroup_id);
            return assigned_permission_object;
        }
    }

    // The group does not have permission.
    return undefined;
}

export function check_group_permission_settings_data(): void {
    const all_realm_group_settings = z
        .array(realm_group_setting_name_schema)
        .parse(Object.keys(realm.server_supported_permission_settings.realm));
    const realm_group_settings_with_subsection_data = new Set<RealmGroupSettingName>([]);
    for (const subsection_obj of settings_config.realm_group_permission_settings) {
        for (const setting_name of subsection_obj.settings) {
            realm_group_settings_with_subsection_data.add(setting_name);
        }
    }

    if (
        !all_realm_group_settings.every((setting_name) =>
            realm_group_settings_with_subsection_data.has(setting_name),
        )
    ) {
        blueslip.error("Settings missing in 'settings_config.realm_group_permission_settings'");
        return;
    }

    const realm_group_setting_label_object_keys = new Set(
        Object.keys(settings_config.all_group_setting_labels.realm),
    );
    if (
        !all_realm_group_settings.every((setting_name) =>
            realm_group_setting_label_object_keys.has(setting_name),
        )
    ) {
        blueslip.error("Settings missing in 'settings_config.all_group_setting_labels.realm'");
        return;
    }

    const all_stream_group_settings = z
        .array(stream_group_setting_name_schema)
        .parse(Object.keys(realm.server_supported_permission_settings.stream));
    const stream_group_permission_settings = new Set(
        settings_config.stream_group_permission_settings,
    );
    if (
        !all_stream_group_settings.every((setting_name) =>
            stream_group_permission_settings.has(setting_name),
        )
    ) {
        blueslip.error("Settings missing in 'settings_config.stream_group_permission_settings'");
        return;
    }

    const stream_group_setting_label_object_keys = new Set(
        Object.keys(settings_config.all_group_setting_labels.stream),
    );
    if (
        !all_stream_group_settings.every((setting_name) =>
            stream_group_setting_label_object_keys.has(setting_name),
        )
    ) {
        blueslip.error("Settings missing in 'settings_config.all_group_setting_labels.stream'");
        return;
    }

    const all_group_group_settings = get_group_permission_settings();
    const group_group_permission_settings = new Set(settings_config.group_permission_settings);
    if (
        !all_group_group_settings.every((setting_name) =>
            group_group_permission_settings.has(setting_name),
        )
    ) {
        blueslip.error("Settings missing in 'settings_config.group_permission_settings'");
        return;
    }

    const group_group_setting_label_object_keys = new Set(
        Object.keys(settings_config.all_group_setting_labels.group),
    );
    if (
        !all_group_group_settings.every((setting_name) =>
            group_group_setting_label_object_keys.has(setting_name),
        )
    ) {
        blueslip.error("Settings missing in 'settings_config.all_group_setting_labels.group'");
        return;
    }
}

export function initialize(): void {
    check_group_permission_settings_data();
}
