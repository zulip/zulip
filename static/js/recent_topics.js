const render_recent_topics_body = require('../templates/recent_topics_table.hbs');
const render_recent_topic_row = require('../templates/recent_topic_row.hbs');
const topics = new Map(); // Key is stream-id:topic.
// Sets the number of avatars to display.
// Rest of the avatars, if present, are displayed as {+x}
const MAX_AVATAR = 4;
let filters = new Set();

exports.process_messages = function (messages) {
    // Since a complete re-render is expensive, we
    // only do it if there are more than 5 messages
    // to process.
    let do_inplace_rerender = true;
    if (messages.length > 5) {
        do_inplace_rerender = false;
    }
    for (const msg of messages) {
        exports.process_message(msg, do_inplace_rerender);
    }
    if (!do_inplace_rerender) {
        exports.complete_rerender();
    }
};

exports.process_message = function (msg, do_inplace_rerender) {
    if (msg.type !== 'stream') {
        return false;
    }
    // Initialize topic data
    const key = msg.stream_id + ':' + msg.topic;
    if (!topics.has(key)) {
        topics.set(key, {
            last_msg_id: -1,
            participated: false,
        });
    }
    // Update topic data
    const is_ours = people.is_my_user_id(msg.sender_id);
    const topic_data = topics.get(key);
    if (topic_data.last_msg_id < msg.id) {
        topic_data.last_msg_id = msg.id;
    }
    topic_data.participated = is_ours || topic_data.participated;

    if (do_inplace_rerender) {
        exports.inplace_rerender(key);
    }
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

function format_topic(topic_data) {
    const last_msg = message_store.get(topic_data.last_msg_id);
    const stream = last_msg.stream;
    const stream_id = last_msg.stream_id;
    const stream_info = stream_data.get_sub(stream);
    const topic = last_msg.topic;
    const time = new XDate(last_msg.timestamp * 1000);
    const last_msg_time = timerender.last_seen_status_from_date(time);

    // We hide the row according to filters or if it's muted.
    let hidden = muting.is_topic_muted(stream_id, topic);
    const unread_count = unread.unread_topic_counter.get(stream_id, topic);
    if (unread_count === 0 && filters.has('unread')) {
        hidden = true;
    }
    if (!topic_data.participated && filters.has('participated')) {
        hidden = true;
    }

    // Display in most recent sender first order
    const all_senders = recent_senders.get_topic_recent_senders(stream_id, topic);
    const senders = all_senders.slice(-MAX_AVATAR);
    const senders_info = people.sender_info_with_small_avatar_urls_for_sender_ids(senders);

    return {
        // stream info
        stream_id: stream_id,
        stream: stream,
        stream_color: stream_info.color,
        invite_only: stream_info.invite_only,
        is_web_public: stream_info.is_web_public,
        stream_url: hash_util.by_stream_uri(stream_id),

        topic: topic,
        unread_count: unread_count,
        last_msg_time: last_msg_time,
        topic_url: hash_util.by_stream_topic_uri(stream_id, topic),
        hidden: hidden,
        senders: senders_info,
        count_senders: Math.max(0, all_senders.length - MAX_AVATAR),
    };
}

function format_all_topics() {
    const topics_array = [];
    for (const [, value] of exports.get()) {
        topics_array.push(format_topic(value));
    }
    return topics_array;
}

function get_topic_row(topic_key) {
    // topic_key = stream_id + ":" + topic
    return $("#" + $.escapeSelector("recent_topic:" + topic_key));
}

exports.inplace_rerender = function (topic_key) {
    // We remove topic from the UI and reinsert it.
    // This makes sure we maintain the correct order
    // of topics.
    const topic_data = topics.get(topic_key);
    if (topic_data === undefined) {
        return false;
    }
    const formatted_values = format_topic(topic_data);
    const topic_row = get_topic_row(topic_key);
    topic_row.remove();

    const rendered_row = render_recent_topic_row(formatted_values);

    const sorted_topic_keys = Array.from(get_sorted_topics().keys());
    const topic_index = sorted_topic_keys.findIndex(
        function (key) {
            if (key === topic_key) {
                return true;
            }
            return false;
        }
    );

    if (topic_index === 0) {
        // Note: In this function length of sorted_topic_keys is always >= 2,
        // since it is called after a complete_rerender has taken place.
        // A complete_rerender only takes place after there is a topic to
        // display. So, this can at min be the second topic we are dealing with.
        get_topic_row(sorted_topic_keys[1]).before(rendered_row);
    }
    get_topic_row(sorted_topic_keys[topic_index - 1]).after(rendered_row);
};

exports.update_topic_is_muted = function (stream_id, topic, is_muted) {
    const key = stream_id + ":" + topic;
    if (!topics.has(key)) {
        // we receive mute request for a topic we are
        // not tracking currently
        return false;
    }

    if (is_muted) {
        get_topic_row(key).hide();
    } else {
        get_topic_row(key).show();
    }
    return true;
};

exports.update_topic_unread_count = function (message) {
    const topic_key = message.stream_id + ":" + message.topic;
    exports.inplace_rerender(topic_key);
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
    exports.complete_rerender();
};

exports.complete_rerender = function () {
    // NOTE: This function is grows expensive with
    // number of topics. Only call when necessary.
    // This functions takes around 1ms per topic to process.
    const rendered_body = render_recent_topics_body({
        recent_topics: format_all_topics(),
        filter_participated: filters.has('participated'),
        filter_unread: filters.has('unread'),
    });
    $('#recent_topics_table').html(rendered_body);

    if (filters.size === 0) {
        $('#recent_topics_filter_buttons')
            .find('[data-filter="all"]')
            .addClass('btn-recent-selected');
    } else {
        for (const filter of filters) {
            $('#recent_topics_filter_buttons')
                .find('[data-filter="' + filter + '"]')
                .addClass('btn-recent-selected');
        }
    }
};

exports.launch = function () {
    overlays.open_overlay({
        name: 'recent_topics',
        overlay: $('#recent_topics_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

window.recent_topics = exports;
