import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import type {User, UserGroupUpdateEvent} from "./types";

type UserGroup = {
    description: string;
    id: number;
    name: string;
    members: Set<number>;
    is_system_group: boolean;
    direct_subgroup_ids: Set<number>;
};

// The members field is a number array which we convert
// to a Set in the initialize function.
type UserGroupRaw = Omit<UserGroup, "members"> & {members: number[]};

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

export function update(event: UserGroupUpdateEvent): void {
    const group = get_user_group_from_id(event.group_id);
    if (event.data.name !== undefined) {
        group.name = event.data.name;
        user_group_name_dict.delete(group.name);
        user_group_name_dict.set(group.name, group);
    }
    if (event.data.description !== undefined) {
        group.description = event.data.description;
        user_group_name_dict.delete(group.name);
        user_group_name_dict.set(group.name, group);
    }
}

export function get_user_group_from_name(name: string): UserGroup | undefined {
    return user_group_name_dict.get(name);
}

export function get_realm_user_groups(): UserGroup[] {
    const user_groups = Array.from(user_group_by_id_dict.values()).sort((a, b) => a.id - b.id);
    return user_groups.filter((group) => !group.is_system_group);
}

export function is_direct_member_of(user_id: number, user_group_id: number): boolean {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error(`Could not find user group with ID ${user_group_id}`);
        return false;
    }
    return user_group.members.has(user_id);
}

export function add_members(user_group_id: number, user_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error(`Could not find user group with ID ${user_group_id}`);
        return;
    }

    for (const user_id of user_ids) {
        user_group.members.add(user_id);
    }
}

export function remove_members(user_group_id: number, user_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error(`Could not find user group with ID ${user_group_id}`);
        return;
    }

    for (const user_id of user_ids) {
        user_group.members.delete(user_id);
    }
}

export function add_subgroups(user_group_id: number, subgroup_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error(`Could not find user group with ID ${user_group_id}`);
        return;
    }

    for (const subgroup_id of subgroup_ids) {
        user_group.direct_subgroup_ids.add(subgroup_id);
    }
}

export function remove_subgroups(user_group_id: number, subgroup_ids: number[]): void {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error(`Could not find user group with ID ${user_group_id}`);
        return;
    }

    for (const subgroup_id of subgroup_ids) {
        user_group.direct_subgroup_ids.delete(subgroup_id);
    }
}

export function initialize(params: {realm_user_groups: UserGroupRaw[]}): void {
    for (const user_group of params.realm_user_groups) {
        add(user_group);
    }
}

export function is_user_group(item: User | UserGroup): item is UserGroup {
    return item.members !== undefined;
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
            blueslip.error(`Could not find subgroup with ID ${subgroup_id}`);
            return undefined;
        }

        for (const direct_subgroup_id of subgroup.direct_subgroup_ids) {
            subgroup_ids.add(direct_subgroup_id);
        }
    }
    return subgroup_ids;
}

export function is_user_in_group(user_group_id: number, user_id: number): boolean {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error(`Could not find user group with ID ${user_group_id}`);
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
