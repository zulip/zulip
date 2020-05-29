const render_recent_topics_body = require('../templates/recent_topics_table.hbs');
const render_recent_topic_row = require('../templates/recent_topic_row.hbs');
const render_recent_topics_filters = require('../templates/recent_topics_filters.hbs');
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
    if (!do_inplace_rerender && overlays.recent_topics_open()) {
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
        // NOTE: This also stores locally echoed msg_id which
        // has not been successfully received from the server.
        // We store it now and reify it when response is available
        // from server.
        topic_data.last_msg_id = msg.id;
    }
    topic_data.participated = is_ours || topic_data.participated;

    if (do_inplace_rerender && overlays.recent_topics_open()) {
        exports.inplace_rerender(key);
    }
    return true;
};

exports.reify_message_id_if_available = function (opts) {
    for (const [, value] of topics.entries()) {
        if (value.last_msg_id === opts.old_id) {
            value.last_msg_id = opts.new_id;
            return true;
        }
    }
    return false;
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


function format_topic(topic_data) {
    const last_msg = message_store.get(topic_data.last_msg_id);
    const stream = last_msg.stream;
    const stream_id = last_msg.stream_id;
    const stream_info = stream_data.get_sub(stream);
    const topic = last_msg.topic;
    const time = new XDate(last_msg.timestamp * 1000);
    const last_msg_time = timerender.last_seen_status_from_date(time);

    // We hide the row according to filters or if it's muted.
    // We only supply the data to the topic rows and let jquery
    // display / hide them according to filters instead of
    // doing complete re-render.
    const topic_muted = !!muting.is_topic_muted(stream_id, topic);
    const stream_muted = stream_data.is_muted(stream_id);
    const muted = topic_muted || stream_muted;
    const unread_count = unread.unread_topic_counter.get(stream_id, topic);

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
        senders: senders_info,
        count_senders: Math.max(0, all_senders.length - MAX_AVATAR),
        muted: muted,
        topic_muted: topic_muted,
        participated: topic_data.participated,
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

exports.process_topic_edit = function (old_stream_id, old_topic, new_topic, new_stream_id) {
    // See `recent_senders.process_topic_edit` for
    // logic behind this and important notes on use of this function.
    topics.delete(old_stream_id + ':' + old_topic);
    get_topic_row(old_stream_id + ':' + old_topic).remove();

    const old_topic_msgs = message_util.get_messages_in_topic(old_stream_id, old_topic);
    exports.process_messages(old_topic_msgs);

    new_stream_id = new_stream_id || old_stream_id;
    const new_topic_msgs = message_util.get_messages_in_topic(new_stream_id, new_topic);
    exports.process_messages(new_topic_msgs);
};

function is_row_hidden(data) {
    const {participated, muted, unreadCount} = data;
    if (unreadCount === 0 && filters.has('unread')) {
        return true;
    } else if (!participated && filters.has('participated')) {
        return true;
    } else if (muted && !filters.has('muted')) {
        return true;
    }
    return false;
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
    let topic_row = get_topic_row(topic_key);
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

    topic_row = get_topic_row(topic_key);
    if (is_row_hidden(topic_row.data())) {
        topic_row.hide();
    } else {
        topic_row.show();
    }
};

exports.update_topic_is_muted = function (stream_id, topic) {
    const key = stream_id + ":" + topic;
    if (!topics.has(key)) {
        // we receive mute request for a topic we are
        // not tracking currently
        return false;
    }

    exports.inplace_rerender(key);
    return true;
};

exports.update_topic_unread_count = function (message) {
    if (overlays.recent_topics_open()) {
        const topic_key = message.stream_id + ":" + message.topic;
        exports.inplace_rerender(topic_key);
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
};

function show_selected_filters() {
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
}

exports.update_filters_view = function () {
    const $rows = $('.recent_topics_table tr').slice(1);
    const search_val = $('#recent_topics_search').val();
    $rows.each(function () {
        const row = $(this);
        if (is_row_hidden(row.data())) {
            row.hide();
        } else {
            row.show();
        }
    });
    exports.search_keyword(search_val);

    const rendered_filters = render_recent_topics_filters({
        filter_participated: filters.has('participated'),
        filter_unread: filters.has('unread'),
        filter_muted: filters.has('muted'),
    });
    $("#recent_filters_group").html(rendered_filters);

    show_selected_filters();
};

exports.search_keyword = function (keyword) {
    if (keyword === "") {
        return false;
    }
    // take all rows and slice off the header.
    const $rows = $('.recent_topics_table tr').slice(1);
    // split the search text around whitespace(s).
    // eg: "Denamark recent" -> ["Denamrk", "recent"]
    const search_keywords = $.trim(keyword).split(/\s+/);
    // turn the search keywords into word boundry groups
    // eg: ["Denamrk", "recent"] -> "^(?=.*\bDenmark\b)(?=.*\brecent\b).*$"
    const val = '^(?=.*\\b' + search_keywords.join('\\b)(?=.*\\b') + ').*$';
    const reg = RegExp(val, 'i'); // i for ignorecase
    let text;

    $rows.filter(function () {
        text = $(this).text().replace(/\s+/g, ' ');
        return !reg.test(text);
    }).hide();
};

exports.complete_rerender = function () {
    // NOTE: This function is grows expensive with
    // number of topics. Only call when necessary.
    // This functions takes around 1ms per topic to process.
    const rendered_body = render_recent_topics_body({
        recent_topics: format_all_topics(),
        filter_participated: filters.has('participated'),
        filter_unread: filters.has('unread'),
        filter_muted: filters.has('muted'),
    });
    $('#recent_topics_table').html(rendered_body);
    exports.update_filters_view();
};

exports.launch = function () {
    recent_topics.complete_rerender();
    overlays.open_overlay({
        name: 'recent_topics',
        overlay: $('#recent_topics_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
};

window.recent_topics = exports;
