"use strict";

const XDate = require("xdate");

const {FoldDict} = require("./fold_dict");

const muted_topics = new Map();

exports.add_muted_topic = function (stream_id, topic, date_muted) {
    let sub_dict = muted_topics.get(stream_id);
    if (!sub_dict) {
        sub_dict = new FoldDict();
        muted_topics.set(stream_id, sub_dict);
    }
    let time = date_muted * 1000;
    if (!date_muted) {
        time = Date.now();
    }
    sub_dict.set(topic, time);
};

exports.remove_muted_topic = function (stream_id, topic) {
    const sub_dict = muted_topics.get(stream_id);
    if (sub_dict) {
        sub_dict.delete(topic);
    }
};

exports.is_topic_muted = function (stream_id, topic) {
    if (stream_id === undefined) {
        return false;
    }
    const sub_dict = muted_topics.get(stream_id);
    return sub_dict && sub_dict.get(topic);
};

exports.get_muted_topics = function () {
    const topics = [];
    for (const [stream_id, sub_dict] of muted_topics) {
        const stream = stream_data.maybe_get_stream_name(stream_id);
        for (const topic of sub_dict.keys()) {
            const date_muted = sub_dict.get(topic);
            const date_muted_str = timerender.render_now(new XDate(date_muted)).time_str;
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
};

exports.set_muted_topics = function (tuples) {
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

        exports.add_muted_topic(stream_id, topic, date_muted);
    }
};

exports.initialize = function () {
    exports.set_muted_topics(page_params.muted_topics);
};

window.muting = exports;
