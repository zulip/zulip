const topics = new Map(); // Key is stream-id:topic.

exports.process_messages = function (messages) {
    for (const msg of messages) {
        exports.process_message(msg);
    }
};

exports.process_message = function (msg) {
    if (msg.type !== 'stream') {
        return false;
    }
    // Initialize topic data
    const key = msg.stream_id + ':' + msg.topic;
    if (!topics.has(key)) {
        topics.set(key, {
            last_msg_id: -1,
            starred: new Set(),
            participated: false,
            muted: false,
        });
    }
    // Update topic data
    const is_ours = people.is_my_user_id(msg.sender_id);
    const topic_data = topics.get(key);
    if (topic_data.last_msg_id < msg.id) {
        topic_data.last_msg_id = msg.id;
    }
    if (msg.starred) {
        topic_data.starred.add(msg.id);
    }
    topic_data.participated = is_ours || topic_data.participated;
    topic_data.muted = topic_data.muted || muting.is_topic_muted(msg.stream_id, msg.topic);
    return true;
};

function get_sorted_topics() {
    // Sort all recent topics by last message time.
    return new Map(Array.from(topics.entries()).sort(function (a, b) {
        return  b[1].last_msg_id -  a[1].last_msg_id;
    }));
}

exports.get = function () {
    return get_sorted_topics();
};

window.recent_topics = exports;
