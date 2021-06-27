import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import {page_params} from "./page_params";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";
import {get_time_from_date_muted} from "./util";

const muted_topics = new Map();

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

export function initialize() {
    set_muted_topics(page_params.muted_topics);
}
