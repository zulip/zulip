const util = require("./util");
const render_recent_topics_body = require('../templates/recent_topics_list.hbs');

let filters = new Set();
const topics = new Map(); // Key is stream-id:topic.
const MAX_AVATAR = 3;  // Number of avatars to display

exports.process_messages = function (messages) {
    messages.forEach(exports.process_message);
    // exports.update() is called via this call too
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
        starred: msg.starred,
    };
}

exports.process_message = function (msg) {
    const is_ours = people.is_my_user_id(msg.sender_id);
    // only process stream msgs in which current user's msg is present.
    const is_relevant = msg.type === 'stream';
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
            starred: msg.starred ? new Set([msg.id]) : new Set(),
            participated: is_ours,
        });
        return true;
    }
    // Update last messages sent to topic.
    if (topic.last_msg.timestamp <= msg.timestamp) {
        topic.last_msg = reduce_message(msg);
    }

    if (msg.starred) {
        topic.starred.add(msg.id);
    }
    topic.participated = is_ours || topic.participated;
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
    exports.update();
};

exports.toggle_bookmark_topic = function (stream_id, topic) {
    // We simply star the last msg in the topic
    // until native support for bookmark is available
    const key = stream_id + ":" + topic;
    const saved_topic = topics.get(key);
    if (saved_topic.starred.size !== 0) {
        starred_messages.unstar_topic(stream_id, topic);
    } else {
        const message = message_store.get(saved_topic.last_msg.id);
        message_flags.toggle_starred_and_update_server(message);
    }
};

exports.change_starred = function (msg_id, flag) {
    const message = message_store.get(msg_id);
    const key = message.stream_id + ':' + message.topic;

    const saved_topic = topics.get(key);
    if (saved_topic === undefined) {
        return;
    }

    if (flag === 'add') {
        saved_topic.starred.add(msg_id);
    } else {
        saved_topic.starred.delete(msg_id);
    }
    topics.set(key, saved_topic);
};

exports.process_topic = function (stream_id, topic) {
    // Delete topic if it exists
    // and procoess it again, this ensures that we haven't
    // missed processing any msg.
    topics.delete(stream_id + ':' + topic);
    const msgs = util.get_messages_in_topic(stream_id, topic);
    exports.process_messages(msgs);
};

function format_values() {
    const topics_array = [];
    exports.get().forEach(function (elem, key) {
        const stream_name = stream_data.maybe_get_stream_name(
            elem.last_msg.stream_id) || elem.last_msg.stream_name;
        const stream_id = parseInt(key.split(':')[0], 10);
        const topic = key.split(':')[1];

        const unread_count = unread.unread_topic_counter.get(stream_id, topic);
        if (unread_count === 0 && filters.has('unread')) {
            return;
        }

        const bookmarked = elem.starred.size !== 0;
        if (!bookmarked && filters.has('bookmarked')) {
            return;
        }
        if (!elem.participated && filters.has('participated')) {
            return;
        }
        // Display in most recent sender first order
        const all_senders = recent_senders.get_topic_recent_senders(
            stream_id, topic);
        const senders = all_senders.slice(-MAX_AVATAR);
        const senders_info = [];
        senders.forEach((id) => {
            const sender = people.get_by_user_id(id);
            sender.avatar_url = people.small_avatar_url_for_person(sender);
            senders_info.push(sender);
        });

        const time = new XDate(elem.last_msg.timestamp * 1000);
        const time_stamp = timerender.last_seen_status_from_date(time);
        topics_array.push({
            stream_id: stream_id,
            stream_name: stream_name,
            topic: topic,
            unread_count: unread_count,
            timestamp: time_stamp,
            stream_url: hash_util.by_stream_uri(stream_id),
            topic_url: hash_util.by_stream_topic_uri(stream_id, topic),
            senders: senders_info,
            count_senders: Math.max(0, all_senders.length - MAX_AVATAR),
            bookmarked: bookmarked,
        });
    });
    return topics_array;
}

exports.update = function () {
    const rendered_body = render_recent_topics_body({
        recent_topics: format_values(),
    });
    $('#recent_topics_table').html(rendered_body);

    if (filters.size === 0) {
        $('#recent_topics_filter_buttons')
            .find('[data-filter="all"]')
            .addClass('btn-recent-selected');
    } else {
        filters.forEach(function (filter) {
            $('#recent_topics_filter_buttons')
                .find('[data-filter="' + filter + '"]')
                .addClass('btn-recent-selected');
        });
    }
};

exports.set_filter = function (filter) {
    const filter_elem = $('#recent_topics_filter_buttons')
        .find('[data-filter="' + filter + '"]');

    if (filter === 'all' && filters.size !== 0) {
        filters = new Set();
    } else if (filter_elem.hasClass('btn-recent-selected')) {
        filters.delete(filter);
    } else {
        filters.add(filter);
    }
    exports.update();
};

exports.launch = function () {
    exports.update();

    overlays.open_overlay({
        name: 'recents',
        overlay: $('#recent_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

window.recent_topics = exports;
