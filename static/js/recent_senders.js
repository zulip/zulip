var recent_senders = (function () {

var exports = {};

var senders = new Dict(); // key is stream-id, value is Dict

exports.process_message_for_senders = function (message) {
    var stream_id = message.stream_id.toString();
    var topic_dict = senders.get(stream_id) || new Dict({fold_case: true});
    var sender_timestamps = topic_dict.get(message.subject) || new Dict();
    var old_timestamp = sender_timestamps.get(message.sender_id);

    if (old_timestamp === undefined || old_timestamp < message.timestamp) {
        sender_timestamps.set(message.sender_id, message.timestamp);
    }

    topic_dict.set(message.subject, sender_timestamps);
    senders.set(stream_id, topic_dict);
};

exports.compare_by_recency = function (user_a, user_b, stream_id, topic) {
    stream_id = stream_id.toString();

    var topic_dict = senders.get(stream_id);
    if (topic_dict !== undefined) {
        var sender_timestamps = topic_dict.get(topic);
        if (sender_timestamps !== undefined) {
            var b_timestamp = sender_timestamps.get(user_b.user_id) || Number.NEGATIVE_INFINITY;
            var a_timestamp = sender_timestamps.get(user_a.user_id) || Number.NEGATIVE_INFINITY;
            return b_timestamp - a_timestamp;
        }
    }

    return 0;
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = recent_senders;
}
