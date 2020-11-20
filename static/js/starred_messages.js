"use strict";

exports.starred_ids = new Set();
const starred_topics = new Map();

exports.is_topic_starred = function (stream_id, topic) {
    return starred_topics.has(stream_id + ":" + topic.toLowerCase());
};

exports.initialize = function () {
    exports.starred_ids.clear();
    starred_topics.clear();

    for (const id of page_params.starred_messages) {
        exports.starred_ids.add(id);
    }

    // Store messages to be processed by recent topics.
    // This will allow us to show starred topics that were
    // not fetched as part of initial messages fetch.
    const messages = [];
    for (const message_meta_data of page_params.all_starred_messages) {
        message_store.set_message_booleans(message_meta_data);
        message_store.add_message_metadata(message_meta_data);
        const message = message_store.get(message_meta_data.id);
        messages.push(message);
        exports.add_starred_msg_in_topic(message);
    }
    recent_topics.process_messages(messages);

    exports.rerender_ui();
};

exports.add_starred_msg_in_topic = function (message) {
    const topic_key = message.stream_id + ":" + message.topic.toLowerCase();
    let msg_ids = starred_topics.get(topic_key);
    if (msg_ids !== undefined) {
        msg_ids.add(message.id);
    } else {
        msg_ids = new Set([message.id]);
    }
    starred_topics.set(topic_key, msg_ids);

    recent_topics.inplace_rerender(topic_key);
    current_msg_list.rerender();
    floating_recipient_bar.update();
};

exports.remove_starred_msg_in_topic = function (message) {
    const topic_key = message.stream_id + ":" + message.topic.toLowerCase();
    let msg_ids = starred_topics.get(topic_key);
    if (msg_ids !== undefined) {
        msg_ids.delete(message.id);
    } else {
        msg_ids = new Set();
    }
    if (msg_ids.size === 0) {
        starred_topics.delete(topic_key);
    } else {
        starred_topics.set(topic_key, msg_ids);
    }

    recent_topics.inplace_rerender(topic_key);
    current_msg_list.rerender();
    floating_recipient_bar.update();
};

exports.add = function (ids) {
    for (const id of ids) {
        // Since 99.9% of the time this loop would only be called once,
        // we don't have to worry about this being a massive message fetch in loop.
        exports.starred_ids.add(id);
        const message = message_store.get(id);
        if (message === undefined) {
            message_util.fetch_message_with_callback(id, exports.add_starred_msg_in_topic);
        } else {
            exports.add_starred_msg_in_topic(message);
        }
    }

    exports.rerender_ui();
};

exports.remove = function (ids) {
    for (const id of ids) {
        exports.starred_ids.delete(id);
        const message = message_store.get(id);
        if (message === undefined) {
            message_util.fetch_message_with_callback(id, exports.remove_starred_msg_in_topic);
        } else {
            exports.remove_starred_msg_in_topic(message);
        }
    }

    exports.rerender_ui();
};

exports.star_topic = function (topic_key) {
    const topic_data = recent_topics.topics.get(topic_key);
    channel.post({
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: JSON.stringify([topic_data.last_msg_id]),
            flag: "starred",
            op: "add",
        },
    });
};

exports.unstar_topic = function (topic_key) {
    const msg_ids = starred_topics.get(topic_key);
    channel.post({
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: JSON.stringify(Array.from(msg_ids)),
            flag: "starred",
            op: "remove",
        },
    });
};

exports.toggle_star_topic = function (stream_id, topic) {
    const topic_key = stream_id + ":" + topic.toLowerCase();
    const is_starred = starred_topics.has(topic_key);
    if (is_starred) {
        exports.unstar_topic(topic_key);
    } else {
        exports.star_topic(topic_key);
    }
};

exports.get_count = function () {
    return exports.starred_ids.size;
};

exports.get_starred_msg_ids = function () {
    return Array.from(exports.starred_ids);
};

exports.rerender_ui = function () {
    let count = exports.get_count();

    if (!page_params.starred_message_counts) {
        // This essentially hides the count
        count = 0;
    }

    top_left_corner.update_starred_count(count);
};

window.starred_messages = exports;
