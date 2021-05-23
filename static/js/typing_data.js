import * as muted_users from "./muted_users";
import * as util from "./util";

// See docs/subsystems/typing-indicators.md for details on typing indicators.

const pm_typists_dict = new Map();
const stream_typists_dict = new Map();
const inbound_timer_dict = new Map();

export function clear_for_testing() {
    pm_typists_dict.clear();
    stream_typists_dict.clear();
    inbound_timer_dict.clear();
}

function to_int(s) {
    return Number.parseInt(s, 10);
}

export function get_pms_key(group) {
    const ids = util.sorted_ids(group);
    return ids.join(",");
}

export function get_topic_key(stream_id, topic) {
    topic = topic.toLowerCase(); // Topics are case-insensitive
    return JSON.stringify({stream_id, topic});
}

export function get_typist_dict(message_type) {
    if (message_type === "stream") {
        return stream_typists_dict;
    }

    if (message_type === "private") {
        return pm_typists_dict;
    }
    throw new Error(`Unknown message_type: ${message_type}`);
}

export function add_typist(key, typist, message_type) {
    const typist_dict = get_typist_dict(message_type);
    const current = typist_dict.get(key) || [];
    typist = to_int(typist);
    if (!current.includes(typist)) {
        current.push(typist);
    }
    typist_dict.set(key, util.sorted_ids(current));
}

export function remove_typist(key, typist, message_type) {
    const typist_dict = get_typist_dict(message_type);
    let current = typist_dict.get(key) || [];

    typist = to_int(typist);
    if (!current.includes(typist)) {
        return false;
    }

    current = current.filter((user_id) => to_int(user_id) !== to_int(typist));

    typist_dict.set(key, current);
    return true;
}

export function get_group_typists(group) {
    const key = get_pms_key(group);
    const user_ids = pm_typists_dict.get(key) || [];
    return muted_users.filter_muted_user_ids(user_ids);
}

export function get_all_pms_typists() {
    let typists = Array.from(pm_typists_dict.values()).flat();
    typists = util.sorted_ids(typists);
    return muted_users.filter_muted_user_ids(typists);
}

export function get_stream_typists(stream_id, topic) {
    const typists = stream_typists_dict.get(get_topic_key(stream_id, topic)) || [];
    return muted_users.filter_muted_user_ids(typists);
}

// The next functions aren't pure data, but it is easy
// enough to mock the setTimeout/clearTimeout functions.
export function clear_inbound_timer(key) {
    const timer = inbound_timer_dict.get(key);
    if (timer) {
        clearTimeout(timer);
        inbound_timer_dict.set(key, undefined);
    }
}

export function kickstart_inbound_timer(key, delay, callback) {
    clear_inbound_timer(key);
    const timer = setTimeout(callback, delay);
    inbound_timer_dict.set(key, timer);
}
