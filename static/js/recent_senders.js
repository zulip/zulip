var recent_senders = (function () {

var exports = {};

var topic_senders = new Dict(); // key is stream-id, value is Dict
var stream_senders = new Dict(); // key is stream-id, value is Dict

exports.process_message_for_senders = function (message) {
    var stream_id = message.stream_id.toString();

    // Process most recent sender to topic
    var topic_dict = topic_senders.get(stream_id) || new Dict({fold_case: true});
    var sender_timestamps = topic_dict.get(message.subject) || new Dict();
    var old_timestamp = sender_timestamps.get(message.sender_id);

    if (old_timestamp === undefined || old_timestamp < message.timestamp) {
        sender_timestamps.set(message.sender_id, message.timestamp);
    }

    topic_dict.set(message.subject, sender_timestamps);
    topic_senders.set(stream_id, topic_dict);

    // Process most recent sender to whole stream
    sender_timestamps = stream_senders.get(stream_id) || new Dict();
    old_timestamp = sender_timestamps.get(message.sender_id);

    if (old_timestamp === undefined || old_timestamp < message.timestamp) {
        sender_timestamps.set(message.sender_id, message.timestamp);
    }

    stream_senders.set(stream_id, sender_timestamps);
};

exports.compare_by_recency = function (user_a, user_b, stream_id, topic) {
    stream_id = stream_id.toString();

    var a_timestamp;
    var b_timestamp;

    var topic_dict = topic_senders.get(stream_id);
    if (topic !== undefined && topic_dict !== undefined) {
        var sender_timestamps = topic_dict.get(topic);
        if (sender_timestamps !== undefined) {
            b_timestamp = sender_timestamps.get(user_b.user_id) || Number.NEGATIVE_INFINITY;
            a_timestamp = sender_timestamps.get(user_a.user_id) || Number.NEGATIVE_INFINITY;

            if (a_timestamp !== b_timestamp) {
                return b_timestamp - a_timestamp;
            }
        }
    }

    // Check recency for whole stream as tiebreaker
    var stream_dict = stream_senders.get(stream_id);
    if (stream_dict !== undefined) {
        b_timestamp = stream_dict.get(user_b.user_id) || Number.NEGATIVE_INFINITY;
        a_timestamp = stream_dict.get(user_a.user_id) || Number.NEGATIVE_INFINITY;

        if (a_timestamp !== b_timestamp) {
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
