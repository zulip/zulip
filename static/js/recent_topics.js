const render_recent_topics_body = require('../templates/recent_topics_table.hbs');
const render_recent_topic_row = require('../templates/recent_topic_row.hbs');
const render_recent_topics_filters = require('../templates/recent_topics_filters.hbs');
const topics = new Map(); // Key is stream-id:topic.
let topics_widget;
// Sets the number of avatars to display.
// Rest of the avatars, if present, are displayed as {+x}
const MAX_AVATAR = 4;
// This variable can be used to set default filters.
let filters = new Set(['unread', 'participated']);

exports.process_messages = function (messages) {
    // FIX: Currently, we do a complete_rerender everytime
    // we process a new message.
    // While this is inexpensive and handles all the cases itself,
    // the UX can be bad if user wants to scroll down the list as
    // the UI will be returned to the beginning of the list on every
    // update.
    for (const msg of messages) {
        exports.process_message(msg);
    }
    exports.complete_rerender();
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
    // TODO: Add backend support for participated topics.
    // Currently participated === Recently Participated
    // i.e. Only those topics are participated for which we have the user's
    // message fetched in the topic. Ideally we would want this to be attached
    // to topic info fetched from backend, which is currently not a thing.
    topic_data.participated = is_ours || topic_data.participated;
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

function get_topic_row(topic_data) {
    const msg = message_store.get(topic_data.last_msg_id);
    const topic_key = msg.stream_id + ":" + msg.topic;
    return $("#" + $.escapeSelector("recent_topic:" + topic_key));
}

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

function topic_in_search_results(keyword, stream, topic) {
    if (keyword === "") {
        return true;
    }
    // split the search text around whitespace(s).
    // eg: "Denamark recent" -> ["Denamrk", "recent"]
    const search_keywords = $.trim(keyword).split(/\s+/);
    // turn the search keywords into word boundry groups
    // eg: ["Denamrk", "recent"] -> "^(?=.*\bDenmark\b)(?=.*\brecent\b).*$"
    const val = '^(?=.*\\b' + search_keywords.join('\\b)(?=.*\\b') + ').*$';
    const reg = RegExp(val, 'i'); // i for ignorecase
    const text = (stream + " " + topic).replace(/\s+/g, ' ');
    return reg.test(text);
}

function is_topic_hidden(topic_data) {
    const msg = message_store.get(topic_data.last_msg_id);
    const topic_muted = !!muting.is_topic_muted(msg.stream_id, msg.topic);
    const stream_muted = stream_data.is_muted(msg.stream_id);
    const muted = topic_muted || stream_muted;
    const unreadCount = unread.unread_topic_counter.get(msg.stream_id, msg.topic);
    const search_keyword = $("#recent_topics_search").val();

    if (unreadCount === 0 && filters.has('unread')) {
        return true;
    } else if (!topic_data.participated && filters.has('participated')) {
        return true;
    } else if (muted && !filters.has('muted')) {
        return true;
    } else if (!topic_in_search_results(search_keyword, msg.stream, msg.topic)) {
        return true;
    }
    return false;
}

exports.inplace_rerender = function (topic_key) {
    if (!overlays.recent_topics_open()) {
        return false;
    }
    if (!topics.has(topic_key)) {
        return false;
    }

    const topic_data = topics.get(topic_key);
    topics_widget.render_item(topic_data);
    const topic_row = get_topic_row(topic_data);

    if (is_topic_hidden(topic_data)) {
        topic_row.hide();
    } else {
        topic_row.show();
    }
    return true;
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
    const rendered_filters = render_recent_topics_filters({
        filter_participated: filters.has('participated'),
        filter_unread: filters.has('unread'),
        filter_muted: filters.has('muted'),
    });
    $("#recent_filters_group").html(rendered_filters);
    show_selected_filters();

    topics_widget.hard_redraw();
};


function stream_sort(a, b) {
    const a_stream = message_store.get(a.last_msg_id).stream;
    const b_stream = message_store.get(b.last_msg_id).stream;
    if (a_stream > b_stream) {
        return 1;
    } else if (a_stream === b_stream) {
        return 0;
    }
    return -1;
}

function topic_sort(a, b) {
    const a_topic = message_store.get(a.last_msg_id).topic;
    const b_topic = message_store.get(b.last_msg_id).topic;
    if (a_topic > b_topic) {
        return 1;
    } else if (a_topic === b_topic) {
        return 0;
    }
    return -1;
}

exports.complete_rerender = function () {
    if (!overlays.recent_topics_open()) {
        return false;
    }
    // Prepare Header
    const rendered_body = render_recent_topics_body({
        filter_participated: filters.has('participated'),
        filter_unread: filters.has('unread'),
        filter_muted: filters.has('muted'),
        search_val: $("#recent_topics_search").val() || "",
    });
    $('#recent_topics_table').html(rendered_body);
    show_selected_filters();

    // Show topics list
    const container = $('.recent_topics_table table tbody');
    container.empty();
    const mapped_topic_values = Array.from(exports.get().values()).map(function (value) {
        return value;
    });

    topics_widget = list_render.create(container, mapped_topic_values, {
        name: "recent_topics_table",
        parent_container: $("#recent_topics_table"),
        modifier: function (item) {
            return render_recent_topic_row(format_topic(item));
        },
        filter: {
            // We use update_filters_view & is_topic_hidden to do all the
            // filtering for us, which is called using click_handlers.
            predicate: function (topic_data) {
                return !is_topic_hidden(topic_data);
            },
        },
        sort_fields: {
            stream_sort: stream_sort,
            topic_sort: topic_sort,
        },
        html_selector: get_topic_row,
    });
};

exports.launch = function () {
    overlays.open_overlay({
        name: 'recent_topics',
        overlay: $('#recent_topics_overlay'),
        on_close: function () {
            hashchange.exit_overlay();
        },
    });
    exports.complete_rerender();
    $("#recent_topics_search").focus();
};

window.recent_topics = exports;
