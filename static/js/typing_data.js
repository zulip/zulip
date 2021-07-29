import _ from "lodash";

import * as muted_users from "./muted_users";
import * as util from "./util";

// See docs/subsystems/typing-indicators.md for details on typing indicators.

const typist_dct = new Map();
const inbound_timer_dict = new Map();

export function clear_for_testing() {
    typist_dct.clear();
    inbound_timer_dict.clear();
}

function to_int(s) {
    return Number.parseInt(s, 10);
}

function get_key(group) {
    const ids = util.sorted_ids(group);
    return ids.join(",");
}

export function add_typist(group, typist) {
    const key = get_key(group);
    const current = typist_dct.get(key) || [];
    typist = to_int(typist);
    if (!current.includes(typist)) {
        current.push(typist);
    }
    typist_dct.set(key, util.sorted_ids(current));
}

export function remove_typist(group, typist) {
    const key = get_key(group);
    let current = typist_dct.get(key) || [];

    typist = to_int(typist);
    if (!current.includes(typist)) {
        return false;
    }

    current = current.filter((user_id) => to_int(user_id) !== to_int(typist));

    typist_dct.set(key, current);
    return true;
}

export function get_group_typists(group) {
    const key = get_key(group);
    const user_ids = typist_dct.get(key) || [];
    return muted_users.filter_muted_user_ids(user_ids);
}

export function get_all_typists() {
    let typists = Array.from(typist_dct.values()).flat();
    typists = util.sorted_ids(typists);
    typists = _.sortedUniq(typists);
    return muted_users.filter_muted_user_ids(typists);
}

// The next functions aren't pure data, but it is easy
// enough to mock the setTimeout/clearTimeout functions.
export function clear_inbound_timer(group) {
    const key = get_key(group);
    const timer = inbound_timer_dict.get(key);
    if (timer) {
        clearTimeout(timer);
        inbound_timer_dict.set(key, undefined);
    }
}

export function kickstart_inbound_timer(group, delay, callback) {
    const key = get_key(group);
    clear_inbound_timer(group);
    const timer = setTimeout(callback, delay);
    inbound_timer_dict.set(key, timer);
}
