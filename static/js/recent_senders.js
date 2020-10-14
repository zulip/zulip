"use strict";

const {FoldDict} = require("./fold_dict");

// topic_senders[stream_id][topic_id][sender_id] = latest_message_id
const topic_senders = new Map();
// topic_senders[stream_id][sender_id] = latest_message_id
const stream_senders = new Map();

exports.process_message_for_senders = function (message) {
    const stream_id = message.stream_id;
    const topic = message.topic;

    // Process most recent sender to topic
    const topic_dict = topic_senders.get(stream_id) || new FoldDict();
    const topic_sender_message_ids = topic_dict.get(topic) || new Map();
    let old_message_id = topic_sender_message_ids.get(message.sender_id);

    if (old_message_id === undefined || old_message_id < message.id) {
        topic_sender_message_ids.set(message.sender_id, message.id);
    }

    topic_dict.set(topic, topic_sender_message_ids);
    topic_senders.set(stream_id, topic_dict);

    // Process most recent sender to whole stream
    const sender_message_ids = stream_senders.get(stream_id) || new Map();
    old_message_id = sender_message_ids.get(message.sender_id);

    if (old_message_id === undefined || old_message_id < message.id) {
        sender_message_ids.set(message.sender_id, message.id);
    }

    stream_senders.set(stream_id, sender_message_ids);
};

exports.process_topic_edit = function (old_stream_id, old_topic, new_topic, new_stream_id) {
    // When topic-editing occurs, we need to update the set of known
    // senders in each stream/topic pair.  This is complicated by the
    // fact that the event we receive from the server does not
    // communicate which senders were present before-and-after; so our
    // strategy is to just rebuild the data structure for the topic
    // from message_store data.

    // This removes the old topic_dict
    const old_topic_dict = topic_senders.get(old_stream_id);
    old_topic_dict.delete(old_topic);

    // Re-processing every message in both the old and new topics is
    // expensive.  It also potentially loses data, because
    // `message_list.all()` only has contiguous message history, not
    // the complete set of message IDs we've received to the
    // `message_store` from the server (E.g. from when we narrowed to
    // a stream).  But it's the most correct implementation we can
    // sensibly do with existing data structures.
    const old_topic_msgs = message_util.get_messages_in_topic(old_stream_id, old_topic);
    for (const msg of old_topic_msgs) {
        exports.process_message_for_senders(msg);
    }

    // use new_stream_id if topic was moved to a new stream,
    // otherwise we just use old_stream_id, implying that
    // just topic was renamed.
    new_stream_id = new_stream_id || old_stream_id;
    const new_topic_msgs = message_util.get_messages_in_topic(new_stream_id, new_topic);
    for (const msg of new_topic_msgs) {
        exports.process_message_for_senders(msg);
    }

    // Note that we don't delete anything from stream_senders here.
    // Our view is that it's probably better to not do so; users who
    // recently posted to a stream are relevant for typeahead even if
    // the messages were moved to another stream or deleted.
};

exports.update_topics_of_deleted_message_ids = function (message_ids) {
    const topics_to_update = message_util.get_topics_for_message_ids(message_ids);

    for (const [stream_id, topic] of topics_to_update.values()) {
        const topic_dict = topic_senders.get(stream_id);
        topic_dict.delete(topic);
        const topic_msgs = message_util.get_messages_in_topic(stream_id, topic);
        for (const msg of topic_msgs) {
            exports.process_message_for_senders(msg);
        }
    }
};

exports.compare_by_recency = function (user_a, user_b, stream_id, topic) {
    let a_message_id;
    let b_message_id;

    const topic_dict = topic_senders.get(stream_id);
    if (topic !== undefined && topic_dict !== undefined) {
        const sender_message_ids = topic_dict.get(topic);
        if (sender_message_ids !== undefined) {
            b_message_id = sender_message_ids.get(user_b.user_id) || Number.NEGATIVE_INFINITY;
            a_message_id = sender_message_ids.get(user_a.user_id) || Number.NEGATIVE_INFINITY;

            if (a_message_id !== b_message_id) {
                return b_message_id - a_message_id;
            }
        }
    }

    // Check recency for whole stream as tiebreaker
    const stream_dict = stream_senders.get(stream_id);
    if (stream_dict !== undefined) {
        b_message_id = stream_dict.get(user_b.user_id) || Number.NEGATIVE_INFINITY;
        a_message_id = stream_dict.get(user_a.user_id) || Number.NEGATIVE_INFINITY;

        if (a_message_id !== b_message_id) {
            return b_message_id - a_message_id;
        }
    }

    return 0;
};

exports.get_topic_recent_senders = function (stream_id, topic) {
    const topic_dict = topic_senders.get(stream_id);
    if (topic_dict === undefined) {
        return [];
    }

    const sender_message_ids = topic_dict.get(topic);
    if (sender_message_ids === undefined) {
        return [];
    }

    const sorted_senders = Array.from(sender_message_ids.entries()).sort((s1, s2) => s1[1] - s2[1]);
    const recent_senders = [];
    for (const item of sorted_senders) {
        recent_senders.push(item[0]);
    }
    return recent_senders;
};

window.recent_senders = exports;
