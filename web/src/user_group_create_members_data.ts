import _ from "lodash";

import * as people from "./people.ts";
import type {User} from "./people.ts";
import {current_user} from "./state_data.ts";
import * as user_group_components from "./user_group_components.ts";
import * as user_groups from "./user_groups.ts";
import type {UserGroup} from "./user_groups.ts";

let user_id_set: Set<number>;
let soft_remove_user_id_set: Set<number>;
let subgroup_id_set = new Set<number>([]);
let soft_remove_subgroup_id_set = new Set<number>([]);

export function initialize_with_current_user(): void {
    user_id_set = new Set([current_user.user_id]);
    soft_remove_user_id_set = new Set();
}

export function reset_subgroups_data(): void {
    subgroup_id_set = new Set([]);
    soft_remove_subgroup_id_set = new Set<number>([]);
}

export function sorted_members(): (User | UserGroup)[] {
    const users = people.get_users_from_ids([...user_id_set]);
    people.sort_but_pin_current_user_on_top(users);

    const subgroups = [...subgroup_id_set]
        .map((group_id) => user_groups.get_user_group_from_id(group_id))
        .sort(user_group_components.sort_group_member_name);

    return [...subgroups, ...users];
}

export function get_all_user_ids(): number[] {
    const potential_members = people.get_realm_users();
    const user_ids = potential_members.map((user) => user.user_id);
    // sort for determinism
    user_ids.sort((a, b) => a - b);
    return user_ids;
}

export function get_principals(): number[] {
    // Return list of user ids which were selected by user.
    return _.difference([...user_id_set], [...soft_remove_user_id_set]);
}

export function get_subgroups(): number[] {
    return _.difference([...subgroup_id_set], [...soft_remove_subgroup_id_set]);
}

export function get_potential_members(): User[] {
    const potential_members = people.get_realm_users();
    return potential_members.filter((user) => !user_id_set.has(user.user_id));
}

export function get_potential_subgroups(): UserGroup[] {
    const potential_subgroups = user_groups.get_all_realm_user_groups();
    return potential_subgroups.filter((group) => !subgroup_id_set.has(group.id));
}

export function add_user_ids(user_ids: number[]): void {
    for (const user_id of user_ids) {
        if (!user_id_set.has(user_id)) {
            const user = people.maybe_get_user_by_id(user_id);
            if (user) {
                user_id_set.add(user_id);
                // Re-adding a user explicitly will not undo the soft remove on their row.
                // e.g If `Iago` was added as part of a group and crossed out.
                // Now, adding another group with Iago as part of it should not undo the soft remove.
            }
        }
    }
}

export function remove_user_ids(user_ids: number[]): void {
    for (const user_id of user_ids) {
        user_id_set.delete(user_id);
        undo_soft_remove_user_id(user_id);
    }
}

export function sync_user_ids(user_ids: number[]): void {
    user_id_set = new Set(user_ids);
}

export function soft_remove_user_id(user_id: number): void {
    soft_remove_user_id_set.add(user_id);
}

export function undo_soft_remove_user_id(user_id: number): void {
    soft_remove_user_id_set.delete(user_id);
}

export function user_id_in_soft_remove_list(user_id: number): boolean {
    return soft_remove_user_id_set.has(user_id);
}

export function add_subgroup_ids(subgroup_ids: number[]): void {
    for (const subgroup_id of subgroup_ids) {
        if (!subgroup_id_set.has(subgroup_id)) {
            const group = user_groups.get_user_group_from_id(subgroup_id);
            if (group) {
                subgroup_id_set.add(subgroup_id);
            }
        }
    }
}

export function sync_subgroup_ids(subgroup_ids: number[]): void {
    subgroup_id_set = new Set(subgroup_ids);
}

export function soft_remove_subgroup_id(subgroup_id: number): void {
    soft_remove_subgroup_id_set.add(subgroup_id);
}

export function undo_soft_remove_subgroup_id(subgroup_id: number): void {
    soft_remove_subgroup_id_set.delete(subgroup_id);
}

export function subgroup_id_in_soft_remove_list(subgroup_id: number): boolean {
    return soft_remove_subgroup_id_set.has(subgroup_id);
}
