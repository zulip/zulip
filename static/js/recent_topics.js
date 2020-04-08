const render_recent_topics_body = require('../templates/recent_topics_table.hbs');
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

exports.update_topic_is_muted = function (stream_id, topic, is_muted) {
    const key = stream_id + ":" + topic;
    if (!topics.has(key)) {
        return false;
    }
    const topic_data = topics.get(stream_id + ":" + topic);
    topic_data.muted = is_muted;
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

exports.process_topic_edit = function (old_stream_id, old_topic, new_topic, new_stream_id) {
    // See `recent_senders.process_topic_edit` for
    // logic behind this and important notes on use of this function.
    topics.delete(old_stream_id + ':' + old_topic);

    const old_topic_msgs = message_util.get_messages_in_topic(old_stream_id, old_topic);
    exports.process_messages(old_topic_msgs);

    new_stream_id = new_stream_id || old_stream_id;
    const new_topic_msgs = message_util.get_messages_in_topic(new_stream_id, new_topic);
    exports.process_messages(new_topic_msgs);
};

exports.launch = function () {
    const rendered_body = render_recent_topics_body();
    $('#recent_topics_table').html(rendered_body);

    overlays.open_overlay({
        name: 'recent_topics',
        overlay: $('#recent_topics_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

window.recent_topics = exports;
