var recent_streams = (function () {

var exports = {};

var stream_senders = new Dict(); // key is stream-id, value is the last message id

exports.process_message_for_senders = function (message) {
    var stream_id = message.stream_id.toString();

    var old_message_id = stream_senders.get(stream_id);
    if (old_message_id === undefined || old_message_id < message.id) {
        stream_senders.set(stream_id, message.id);
    }
};

exports.compare_by_recency = function(stream_a, stream_b) {
	stream_a = stream_a.toString();
	stream_b = stream_b.toString();

	a_message_id = stream_senders.get(stream_a) || Number.NEGATIVE_INFINITY;
	b_message_id = stream_senders.get(stream_b) || Number.NEGATIVE_INFINITY;
	return b_message_id - a_message_id;
}

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = recent_streams;
}
window.recent_streams = recent_streams;