import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";

let user_group_name_dict;
let user_group_by_id_dict;
let active_user_group_by_id_dict;

// We have an init() function so that our automated tests
// can easily clear data.
export function init() {
    user_group_name_dict = new FoldDict();
    user_group_by_id_dict = new Map();
    active_user_group_by_id_dict = new Map();
}

// WE INITIALIZE DATA STRUCTURES HERE!
init();

export function add(user_group) {
    // Reformat the user group members structure to be a set.
    user_group.members = new Set(user_group.members);
    user_group_name_dict.set(user_group.name, user_group);
    user_group_by_id_dict.set(user_group.id, user_group);
}

export function add_in_realm(user_group) {
    active_user_group_by_id_dict.set(user_group.id, user_group);
    add(user_group);
}

export function remove(user_group) {
    active_user_group_by_id_dict.delete(user_group.id);
}

export function get_user_group_from_id(group_id, suppress_errors) {
    if (!user_group_by_id_dict.has(group_id)) {
        if (suppress_errors === undefined) {
            blueslip.error("Unknown group_id in get_user_group_from_id: " + group_id);
        }
        return undefined;
    }
    return user_group_by_id_dict.get(group_id);
}

export function get_active_user_group_from_id(group_id, suppress_errors) {
    if (!active_user_group_by_id_dict.has(group_id)) {
        if (suppress_errors === undefined) {
            blueslip.error("Unknown group_id in get_active_user_group_from_id: " + group_id);
        }
        return undefined;
    }
    return active_user_group_by_id_dict.get(group_id);
}

export function is_active_user_group(group) {
    return active_user_group_by_id_dict.has(group.id);
}

export function update(event) {
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

export function get_user_group_from_name(name) {
    return user_group_name_dict.get(name);
}

export function get_active_user_group_from_name(name) {
    const active_user_group_name_dict = new FoldDict();
    for (const [name, group] of user_group_name_dict) {
        if (is_active_user_group(group)) {
            active_user_group_name_dict.set(name, group);
        }
    }
    return active_user_group_name_dict.get(name);
}

export function get_realm_user_groups() {
    return Array.from(active_user_group_by_id_dict.values()).sort((a, b) => a.id - b.id);
}

export function is_member_of(user_group_id, user_id) {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group with ID " + user_group_id);
        return false;
    }
    return user_group.members.has(user_id);
}

export function add_members(user_group_id, user_ids) {
    const user_group = user_group_by_id_dict.get(user_group_id);

    for (const user_id of user_ids) {
        user_group.members.add(user_id);
    }
}

export function remove_members(user_group_id, user_ids) {
    const user_group = user_group_by_id_dict.get(user_group_id);

    for (const user_id of user_ids) {
        user_group.members.delete(user_id);
    }
}

export function initialize(params) {
    for (const user_group of params.realm_user_groups) {
        add_in_realm(user_group);
    }
    if (params.realm_non_active_user_groups) {
        for (const user_group of params.realm_non_active_user_groups) {
            add(user_group);
        }
    }
}

export function is_user_group(item) {
    return item.members !== undefined;
}
