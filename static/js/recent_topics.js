const util = require("./util");
const render_recent_topics_body = require('../templates/recent_topics_list.hbs');

const topics = new Map(); // Key is stream-id:topic.

exports.process_messages = function (messages) {
    messages.forEach(exports.process_message);
    exports.update_muted_topics();
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

exports.update_muted_topics = function () {
    for (const elem of muting.get_muted_topics()) {
        const key = elem.stream_id + ':' + elem.topic;
        topics.delete(key);
    }
};

exports.process_topic = function (stream_id, topic) {
    // Delete topic if it exists
    // and procoess it again, this ensures that we haven't
    // missed processing any msg.
    topics.delete(stream_id + ':' + topic);
    const msgs = util.get_messages_in_topic(stream_id, topic);
    exports.process_messages(msgs);
};

exports.launch = function () {
    const rendered_body = render_recent_topics_body();
    $('#recent_topics_table').html(rendered_body);

    overlays.open_overlay({
        name: 'recents',
        overlay: $('#recent_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

window.recent_topics = exports;
