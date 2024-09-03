import assert from "minimalistic-assert";
import type {z} from "zod";

import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import * as group_permission_settings from "./group_permission_settings";
import {$t} from "./i18n";
import {page_params} from "./page_params";
import * as settings_config from "./settings_config";
import type {StateData, user_group_schema} from "./state_data";
import {current_user} from "./state_data";
import type {UserOrMention} from "./typeahead_helper";
import type {UserGroupUpdateEvent} from "./types";

type UserGroupRaw = z.infer<typeof user_group_schema>;

// The members field is a number array which we convert
// to a Set in the initialize function.
export type UserGroup = Omit<UserGroupRaw, "members" | "direct_subgroup_ids"> & {
    members: Set<number>;
    direct_subgroup_ids: Set<number>;
};

type UserGroupForDropdownListWidget = {
    name: string;
    unique_id: number;
};

let user_group_name_dict: FoldDict<UserGroup>;
let user_group_by_id_dict: Map<number, UserGroup>;

// We have an init() function so that our automated tests
// can easily clear data.
export function init(): void {
    user_group_name_dict = new FoldDict();
    user_group_by_id_dict = new Map<number, UserGroup>();
}

// WE INITIALIZE DATA STRUCTURES HERE!
init();

export function add(user_group_raw: UserGroupRaw): void {
    // Reformat the user group members structure to be a set.
    const user_group = {
        description: user_group_raw.description,
        id: user_group_raw.id,
        name: user_group_raw.name,
        members: new Set(user_group_raw.members),
        is_system_group: user_group_raw.is_system_group,
        direct_subgroup_ids: new Set(user_group_raw.direct_subgroup_ids),
        can_manage_group: user_group_raw.can_manage_group,
        can_mention_group: user_group_raw.can_mention_group,
    };

    user_group_name_dict.set(user_group.name, user_group);
    user_group_by_id_dict.set(user_group.id, user_group);
}

export function remove(user_group: UserGroup): void {
    user_group_name_dict.delete(user_group.name);
    user_group_by_id_dict.delete(user_group.id);
}

export function get_user_group_from_id(group_id: number): UserGroup {
    const user_group = user_group_by_id_dict.get(group_id);
    if (!user_group) {
        throw new Error(`Unknown group_id in get_user_group_from_id: ${group_id}`);
    }
    return user_group;
}

export function maybe_get_user_group_from_id(group_id: number): UserGroup | undefined {
    return user_group_by_id_dict.get(group_id);
}

export function update(event: UserGroupUpdateEvent): void {
    const group = get_user_group_from_id(event.group_id);
    if (event.data.name !== undefined) {
        user_group_name_dict.delete(group.name);
        group.name = event.data.name;
        user_group_name_dict.set(group.name, group);
    }
    if (event.data.description !== undefined) {
        group.description = event.data.description;
        user_group_name_dict.delete(group.name);
        user_group_name_dict.set(group.name, group);
    }

    if (event.data.can_mention_group !== undefined) {
        group.can_mention_group = event.data.can_mention_group;
        user_group_name_dict.delete(group.name);
        user_group_name_dict.set(group.name, group);
    }

    if (event.data.can_manage_group !== undefined) {
        group.can_manage_group = event.data.can_manage_group;
        user_group_name_dict.delete(group.name);
        user_group_name_dict.set(group.name, group);
    }
}

export function get_user_group_from_name(name: string): UserGroup | undefined {
    return user_group_name_dict.get(name);
}

export function get_realm_user_groups(): UserGroup[] {
    const user_groups = [...user_group_by_id_dict.values()].sort((a, b) => a.id - b.id);
    return user_groups.filter((group) => !group.is_system_group);
}

export function get_user_groups_allowed_to_mention(): UserGroup[] {
    const user_groups = get_realm_user_groups();
    return user_groups.filter((group) => {
        const can_mention_group_id = group.can_mention_group;
        return is_user_in_group(can_mention_group_id, current_user.user_id);
    });
}

export function is_direct_member_of(user_id: number, user_group_id: number): boolean {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group", {user_group_id});
        return false;
    }
    return user_group.members.has(user_id);
}

export function add_members(user_group_id: number, user_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group", {user_group_id});
        return;
    }

    for (const user_id of user_ids) {
        user_group.members.add(user_id);
    }
}

export function remove_members(user_group_id: number, user_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group", {user_group_id});
        return;
    }

    for (const user_id of user_ids) {
        user_group.members.delete(user_id);
    }
}

export function add_subgroups(user_group_id: number, subgroup_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group", {user_group_id});
        return;
    }

    for (const subgroup_id of subgroup_ids) {
        user_group.direct_subgroup_ids.add(subgroup_id);
    }
}

export function remove_subgroups(user_group_id: number, subgroup_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group", {user_group_id});
        return;
    }

    for (const subgroup_id of subgroup_ids) {
        user_group.direct_subgroup_ids.delete(subgroup_id);
    }
}

export function initialize(params: StateData["user_groups"]): void {
    for (const user_group of params.realm_user_groups) {
        add(user_group);
    }
}

export function is_user_group(
    item: (UserOrMention & {members: undefined}) | UserGroup,
): item is UserGroup {
    return item.members !== undefined;
}

export function is_empty_group(user_group_id: number): boolean {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group", {user_group_id});
        return false;
    }
    if (user_group.members.size > 0) {
        return false;
    }

    // Check if all the recursive subgroups are empty.
    // Correctness of this algorithm relying on the ES6 Set
    // implementation having the property that a `for of` loop will
    // visit all items that are added to the set during the loop.
    const subgroup_ids = new Set(user_group.direct_subgroup_ids);
    for (const subgroup_id of subgroup_ids) {
        const subgroup = user_group_by_id_dict.get(subgroup_id);
        if (subgroup === undefined) {
            blueslip.error("Could not find subgroup", {subgroup_id});
            return false;
        }
        if (subgroup.members.size > 0) {
            return false;
        }
        for (const direct_subgroup_id of subgroup.direct_subgroup_ids) {
            subgroup_ids.add(direct_subgroup_id);
        }
    }
    return true;
}

export function get_user_groups_of_user(user_id: number): UserGroup[] {
    const user_groups_realm = get_realm_user_groups();
    const groups_of_user = user_groups_realm.filter((group) =>
        is_direct_member_of(user_id, group.id),
    );
    return groups_of_user;
}

export function get_recursive_subgroups(target_user_group: UserGroup): Set<number> | undefined {
    // Correctness of this algorithm relying on the ES6 Set
    // implementation having the property that a `for of` loop will
    // visit all items that are added to the set during the loop.
    const subgroup_ids = new Set(target_user_group.direct_subgroup_ids);
    for (const subgroup_id of subgroup_ids) {
        const subgroup = user_group_by_id_dict.get(subgroup_id);
        if (subgroup === undefined) {
            blueslip.error("Could not find subgroup", {subgroup_id});
            return undefined;
        }

        for (const direct_subgroup_id of subgroup.direct_subgroup_ids) {
            subgroup_ids.add(direct_subgroup_id);
        }
    }
    return subgroup_ids;
}

export function get_recursive_group_members(target_user_group: UserGroup): Set<number> {
    const members = new Set(target_user_group.members);
    const subgroup_ids = get_recursive_subgroups(target_user_group);

    if (subgroup_ids === undefined) {
        return members;
    }

    for (const subgroup_id of subgroup_ids) {
        const subgroup = user_group_by_id_dict.get(subgroup_id);
        assert(subgroup !== undefined);
        for (const member of subgroup.members) {
            members.add(member);
        }
    }
    return members;
}

export function is_user_in_group(user_group_id: number, user_id: number): boolean {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group", {user_group_id});
        return false;
    }
    if (is_direct_member_of(user_id, user_group_id)) {
        return true;
    }

    const subgroup_ids = get_recursive_subgroups(user_group);
    if (subgroup_ids === undefined) {
        return false;
    }

    for (const group_id of subgroup_ids) {
        if (is_direct_member_of(user_id, group_id)) {
            return true;
        }
    }
    return false;
}

function get_display_name_for_system_group_option(setting_name: string, name: string): string {
    // We use a special label for the "Nobody" system group for clarity.
    if (setting_name === "direct_message_permission_group" && name === "Nobody") {
        return $t({defaultMessage: "Direct messages disabled"});
    }
    return name;
}

export function get_realm_user_groups_for_dropdown_list_widget(
    setting_name: string,
    setting_type: "realm" | "stream" | "group",
): UserGroupForDropdownListWidget[] {
    const group_setting_config = group_permission_settings.get_group_permission_setting_config(
        setting_name,
        setting_type,
    );

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

    const system_user_groups = settings_config.system_user_groups_list
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
            const user_group = get_user_group_from_name(group.name);
            if (!user_group) {
                throw new Error(`Unknown group name: ${group.name}`);
            }
            return {
                name: get_display_name_for_system_group_option(setting_name, group.display_name),
                unique_id: user_group.id,
            };
        });

    if (
        (setting_name !== "can_mention_group" && !page_params.development_environment) ||
        require_system_group
    ) {
        return system_user_groups;
    }

    const user_groups_excluding_system_groups = get_realm_user_groups().map((group) => ({
        name: group.name,
        unique_id: group.id,
    }));

    return [...system_user_groups, ...user_groups_excluding_system_groups];
}

// Group name for user-facing display. For settings, we already use
// description strings for system groups. But those description strings
// might not be suitable for every case, e.g. we want the name for
// `role:everyone` to be `Everyone` instead of
// `Admins, moderators, members and guests` from `settings_config`.
// Right now, we only change the name for `role:everyone`, that's why
// we don't store the values in a structured way like
// `settings_config` yet.
export function get_display_group_name(user_group: UserGroup): string {
    return user_group.name === "role:everyone" ? $t({defaultMessage: "Everyone"}) : user_group.name;
}
