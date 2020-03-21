const topics = new Map(); // Key is stream-id:topic.

exports.process_messages = function (messages) {
    messages.forEach(exports.process_message);
};

function reduce_message(msg) {
    return {
        id: msg.id,
        timestamp: msg.timestamp,
        stream_id: msg.stream_id,
        stream_name: msg.stream,
        topic: msg.topic,
        sender_id: msg.sender_id,
        type: msg.type,
    };
}

exports.process_message = function (msg) {
    const is_ours = people.is_my_user_id(msg.sender_id);
    // only process stream msgs in which current user's msg is present.
    const is_relevant = is_ours && msg.type === 'stream';
    const key = msg.stream_id + ':' + msg.topic;
    const topic = topics.get(key);
    // Process msg if it's not user's but we are tracking the topic.
    if (topic === undefined && !is_relevant) {
        return false;
    }
    // Add new topic if msg is_relevant
    if (!topic) {
        topics.set(key, {
            last_msg: reduce_message(msg),
        });
        return true;
    }
    // Update last messages sent to topic.
    if (topic.last_msg.timestamp <= msg.timestamp) {
        topic.last_msg = reduce_message(msg);
    }
    topics.set(key, topic);
    return true;
};

function get_sorted_topics() {
    // Sort all recent topics by last message time.
    return new Map(Array.from(topics.entries()).sort(function (a, b) {
        return  b[1].last_msg.timestamp -  a[1].last_msg.timestamp;
    }));
}

exports.get = function () {
    return get_sorted_topics();
};

window.recent_topics = exports;
