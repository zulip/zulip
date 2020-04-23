const FoldDict = require('./fold_dict').FoldDict;

const topic_senders = new Map(); // key is stream-id, value is Map
const stream_senders = new Map(); // key is stream-id, value is Map

exports.process_message_for_senders = function (message) {
    const stream_id = message.stream_id;
    const topic = message.topic;

    // Process most recent sender to topic
    const topic_dict = topic_senders.get(stream_id) || new FoldDict();
    let sender_message_ids = topic_dict.get(topic) || new Map();
    let old_message_id = sender_message_ids.get(message.sender_id);

    if (old_message_id === undefined || old_message_id < message.id) {
        sender_message_ids.set(message.sender_id, message.id);
    }

    topic_dict.set(topic, sender_message_ids);
    topic_senders.set(stream_id, topic_dict);

    // Process most recent sender to whole stream
    sender_message_ids = stream_senders.get(stream_id) || new Map();
    old_message_id = sender_message_ids.get(message.sender_id);

    if (old_message_id === undefined || old_message_id < message.id) {
        sender_message_ids.set(message.sender_id, message.id);
    }

    stream_senders.set(stream_id, sender_message_ids);
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
    let sender_message_ids = new Map();
    if (topic_dict !== undefined) {
        sender_message_ids = topic_dict.get(topic);
    }
    const sorted_senders = Array.from(sender_message_ids.entries()).sort(
        (s1, s2) => { return s1[1] - s2[1]; }
    );
    const recent_senders = [];
    sorted_senders.forEach((item) => { recent_senders.push(item[0]); });
    return recent_senders;
};

window.recent_senders = exports;
