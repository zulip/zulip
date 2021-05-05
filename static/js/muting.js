import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";

const muted_topics = new Map();
const muted_users = new Map();

function get_time_from_date_muted(date_muted) {
    if (date_muted === undefined) {
        return Date.now();
    }
    return date_muted * 1000;
}

export function add_muted_topic(stream_id, topic, date_muted) {
    let sub_dict = muted_topics.get(stream_id);
    if (!sub_dict) {
        sub_dict = new FoldDict();
        muted_topics.set(stream_id, sub_dict);
    }
    const time = get_time_from_date_muted(date_muted);
    sub_dict.set(topic, time);
}

export function remove_muted_topic(stream_id, topic) {
    const sub_dict = muted_topics.get(stream_id);
    if (sub_dict) {
        sub_dict.delete(topic);
    }
}

export function is_topic_muted(stream_id, topic) {
    if (stream_id === undefined) {
        return false;
    }
    const sub_dict = muted_topics.get(stream_id);
    return (sub_dict && sub_dict.get(topic)) || false;
}

export function get_muted_topics() {
    const topics = [];
    for (const [stream_id, sub_dict] of muted_topics) {
        const stream = stream_data.maybe_get_stream_name(stream_id);
        for (const topic of sub_dict.keys()) {
            const date_muted = sub_dict.get(topic);
            const date_muted_str = timerender.render_now(new Date(date_muted)).time_str;
            topics.push({
                stream_id,
                stream,
                topic,
                date_muted,
                date_muted_str,
            });
        }
    }
    return topics;
}

export function set_muted_topics(tuples) {
    muted_topics.clear();

    for (const tuple of tuples) {
        const stream_name = tuple[0];
        const topic = tuple[1];
        const date_muted = tuple[2];

        const stream_id = stream_data.get_stream_id(stream_name);

        if (!stream_id) {
            blueslip.warn("Unknown stream in set_muted_topics: " + stream_name);
            continue;
        }

        add_muted_topic(stream_id, topic, date_muted);
    }
}

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
    set_muted_topics(page_params.muted_topics);
    set_muted_users(page_params.muted_users);
}
