import {page_params} from "./page_params";
import * as timerender from "./timerender";
import {get_time_from_date_muted} from "./util";

const muted_users = new Map();

export function add_muted_user(user_id, date_muted) {
    const time = get_time_from_date_muted(date_muted);
    if (user_id) {
        muted_users.set(user_id, time);
    }
}

export function remove_muted_user(user_id) {
    if (user_id) {
        muted_users.delete(user_id);
    }
}

export function is_user_muted(user_id) {
    if (user_id === undefined) {
        return false;
    }

    return muted_users.has(user_id);
}

export function filter_muted_user_ids(user_ids) {
    // Returns a copy of the user ID list, after removing muted user IDs.
    const base_user_ids = [...user_ids];
    return base_user_ids.filter((user_id) => !is_user_muted(user_id));
}

export function filter_muted_users(persons) {
    // Returns a copy of the people list, after removing muted users.
    const base_users = [...persons];
    return base_users.filter((person) => !is_user_muted(person.user_id));
}

export function get_muted_users() {
    const users = [];
    for (const [id, date_muted] of muted_users) {
        const date_muted_str = timerender.render_now(new Date(date_muted)).time_str;
        users.push({
            id,
            date_muted,
            date_muted_str,
        });
    }
    return users;
}

export function set_muted_users(list) {
    muted_users.clear();

    for (const user of list) {
        if (user !== undefined && user.id !== undefined) {
            add_muted_user(user.id, user.timestamp);
        }
    }
}

export function initialize() {
    set_muted_users(page_params.muted_users);
}
