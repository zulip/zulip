import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";
import {get_time_from_date_muted} from "./util";

const muted_topics = new Map();

export const visibility_policy = {
    VISIBILITY_POLICY_INHERIT: 0,
    MUTED: 1,
    UNMUTED: 2,
    FOLLOWED: 3,
};

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

export function set_user_topic(user_topic) {
    const stream_id = user_topic.stream_id;
    const topic = user_topic.topic_name;
    const date_muted = user_topic.last_updated;

    const stream_name = stream_data.maybe_get_stream_name(stream_id);

    if (!stream_name) {
        blueslip.warn("Unknown stream ID in set_user_topic: " + stream_id);
        return;
    }

    switch (user_topic.visibility_policy) {
        case visibility_policy.MUTED:
            add_muted_topic(stream_id, topic, date_muted);
            break;
        case visibility_policy.VISIBILITY_POLICY_INHERIT:
            remove_muted_topic(stream_id, topic);
            break;
    }
}

export function set_user_topics(user_topics) {
    muted_topics.clear();

    for (const user_topic of user_topics) {
        set_user_topic(user_topic);
    }
}

export function initialize() {
    set_user_topics(page_params.user_topics);
}
