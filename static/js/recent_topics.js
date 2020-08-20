"use strict";

const XDate = require("xdate");

const render_recent_topic_row = require("../templates/recent_topic_row.hbs");
const render_recent_topics_filters = require("../templates/recent_topics_filters.hbs");
const render_recent_topics_body = require("../templates/recent_topics_table.hbs");

const people = require("./people");

const topics = new Map(); // Key is stream-id:topic.
let topics_widget;
// Sets the number of avatars to display.
// Rest of the avatars, if present, are displayed as {+x}
const MAX_AVATAR = 4;
let filters = new Set();

// Use this to set the focused element.
//
// We set it's value to `table` in case the
// focus in one of the table rows, since the
// table rows are constantly updated and tracking
// the selected element in them would be tedious via
// jquery.
//
// So, we use table as a grid system and
// track the coordinates of the focus element via
// `row_focus` and `col_focus`.
let current_focus_elem;
let row_focus = 0;
// Start focus on the topic column, so Down+Enter works to visit a topic.
let col_focus = 1;

// The number of selectable actions in a recent_topics.  Used to
// implement wraparound of elements with the right/left keys.  Must be
// increased when we add new actions, or rethought if we add optional
// actions that only appear in some rows.
const MAX_SELECTABLE_COLS = 4;

function set_default_focus() {
    // If at any point we are confused about the currently
    // focused element, we switch focus to search.
    current_focus_elem = $("#recent_topics_search");
    current_focus_elem.trigger("focus");
}

function set_table_focus(row, col) {
    const topic_rows = $("#recent_topics_table table tbody tr");
    if (topic_rows.length === 0 || row < 0 || row >= topic_rows.length) {
        row_focus = 0;
        // return focus back to filters if we cannot focus on the table.
        set_default_focus();
        return true;
    }

    topic_rows.eq(row).find(".recent_topics_focusable").eq(col).children().trigger("focus");
    current_focus_elem = "table";
    return true;
}

function revive_current_focus() {
    // After re-render, the current_focus_elem is no longer linked
    // to the focused element, this function attempts to revive the
    // link and focus to the element prior to the rerender.
    if (!current_focus_elem) {
        set_default_focus();
        return false;
    }

    if (current_focus_elem === "table") {
        set_table_focus(row_focus, col_focus);
        return true;
    }

    const filter_button = current_focus_elem.data("filter");
    if (!filter_button) {
        set_default_focus();
    } else {
        current_focus_elem = $("#recent_topics_filter_buttons").find(
            "[data-filter='" + filter_button + "']",
        );
        current_focus_elem.trigger("focus");
    }
    return true;
}

function get_topic_key(stream_id, topic) {
    return stream_id + ":" + topic.toLowerCase();
}

exports.process_messages = function (messages) {
    // FIX: Currently, we do a complete_rerender every time
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
    if (msg.type !== "stream") {
        return false;
    }
    // Initialize topic data
    const key = get_topic_key(msg.stream_id, msg.topic);
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
    // We don't need to reify the message_id of the topic
    // if a new message arrives in the topic from another user,
    // since it replaces the last_msg_id of the topic which
    // we were trying to reify.
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
    return new Map(
        Array.from(topics.entries()).sort((a, b) => b[1].last_msg_id - a[1].last_msg_id),
    );
}

exports.get = function () {
    return get_sorted_topics();
};

function format_topic(topic_data) {
    const last_msg = message_store.get(topic_data.last_msg_id);
    const stream = last_msg.stream;
    const stream_id = last_msg.stream_id;
    const stream_info = stream_data.get_sub_by_id(stream_id);
    if (stream_info === undefined) {
        // stream was deleted
        return {};
    }
    const topic = last_msg.topic;
    const time = new XDate(last_msg.timestamp * 1000);
    const last_msg_time = timerender.last_seen_status_from_date(time);
    const full_datetime = timerender.get_full_datetime(time);

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
        stream_id,
        stream,
        stream_color: stream_info.color,
        invite_only: stream_info.invite_only,
        is_web_public: stream_info.is_web_public,
        stream_url: hash_util.by_stream_uri(stream_id),

        topic,
        topic_key: get_topic_key(stream_id, topic),
        unread_count,
        last_msg_time,
        topic_url: hash_util.by_stream_topic_uri(stream_id, topic),
        senders: senders_info,
        other_senders_count: Math.max(0, all_senders.length - MAX_AVATAR),
        muted,
        topic_muted,
        participated: topic_data.participated,
        full_last_msg_date_time: full_datetime.date + " " + full_datetime.time,
    };
}

function get_topic_row(topic_data) {
    const msg = message_store.get(topic_data.last_msg_id);
    const topic_key = get_topic_key(msg.stream_id, msg.topic);
    return $("#" + $.escapeSelector("recent_topic:" + topic_key));
}

exports.process_topic_edit = function (old_stream_id, old_topic, new_topic, new_stream_id) {
    // See `recent_senders.process_topic_edit` for
    // logic behind this and important notes on use of this function.
    topics.delete(get_topic_key(old_stream_id, old_topic));

    const old_topic_msgs = message_util.get_messages_in_topic(old_stream_id, old_topic);
    exports.process_messages(old_topic_msgs);

    new_stream_id = new_stream_id || old_stream_id;
    const new_topic_msgs = message_util.get_messages_in_topic(new_stream_id, new_topic);
    exports.process_messages(new_topic_msgs);
};

exports.topic_in_search_results = function (keyword, stream, topic) {
    if (keyword === "") {
        return true;
    }
    const text = (stream + " " + topic).toLowerCase();
    const search_words = keyword.toLowerCase().split(/\s+/);
    return search_words.every((word) => text.includes(word));
};

exports.update_topics_of_deleted_message_ids = function (message_ids) {
    const topics_to_rerender = new Map();
    for (const msg_id of message_ids) {
        const message = message_store.get(msg_id);
        if (message === undefined) {
            // We may not have the deleted message cached locally in
            // message_store; if so, we can just skip processing it.
            continue;
        }
        if (message.type === "stream") {
            const topic_key = get_topic_key(message.stream_id, message.topic);
            topics_to_rerender.set(topic_key, [message.stream_id, message.topic]);
        }
    }

    for (const [stream_id, topic] of topics_to_rerender.values()) {
        topics.delete(get_topic_key(stream_id, topic));
        const msgs = message_util.get_messages_in_topic(stream_id, topic);
        exports.process_messages(msgs);
    }
};

exports.filters_should_hide_topic = function (topic_data) {
    const msg = message_store.get(topic_data.last_msg_id);

    if (stream_data.get_sub_by_id(msg.stream_id) === undefined) {
        // Never try to process deactivated streams.
        return true;
    }

    if (filters.has("unread")) {
        const unreadCount = unread.unread_topic_counter.get(msg.stream_id, msg.topic);
        if (unreadCount === 0) {
            return true;
        }
    }

    if (!topic_data.participated && filters.has("participated")) {
        return true;
    }

    if (!filters.has("include_muted")) {
        const topic_muted = !!muting.is_topic_muted(msg.stream_id, msg.topic);
        const stream_muted = stream_data.is_muted(msg.stream_id);
        if (topic_muted || stream_muted) {
            return true;
        }
    }

    const search_keyword = $("#recent_topics_search").val();
    if (!recent_topics.topic_in_search_results(search_keyword, msg.stream, msg.topic)) {
        return true;
    }

    return false;
};

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

    if (exports.filters_should_hide_topic(topic_data)) {
        topic_row.hide();
    } else {
        topic_row.show();
    }
    revive_current_focus();
    return true;
};

exports.update_topic_is_muted = function (stream_id, topic) {
    const key = get_topic_key(stream_id, topic);
    if (!topics.has(key)) {
        // we receive mute request for a topic we are
        // not tracking currently
        return false;
    }

    exports.inplace_rerender(key);
    return true;
};

exports.update_topic_unread_count = function (message) {
    const topic_key = get_topic_key(message.stream_id, message.topic);
    exports.inplace_rerender(topic_key);
};

exports.set_filter = function (filter) {
    // This function updates the `filters` variable
    // after user clicks on one of the filter buttons
    // based on `btn-recent-selected` class and current
    // set `filters`.

    // Get the button which was clicked.
    const filter_elem = $("#recent_topics_filter_buttons").find('[data-filter="' + filter + '"]');

    // If user clicks `All`, we clear all filters.
    if (filter === "all" && filters.size !== 0) {
        filters = new Set();
        // If the button was already selected, remove the filter.
    } else if (filter_elem.hasClass("btn-recent-selected")) {
        filters.delete(filter);
        // If the button was not selected, we add the filter.
    } else {
        filters.add(filter);
    }
};

function show_selected_filters() {
    // Add `btn-selected-filter` to the buttons to show
    // which filters are applied.
    if (filters.size === 0) {
        $("#recent_topics_filter_buttons")
            .find('[data-filter="all"]')
            .addClass("btn-recent-selected");
    } else {
        for (const filter of filters) {
            $("#recent_topics_filter_buttons")
                .find('[data-filter="' + filter + '"]')
                .addClass("btn-recent-selected");
        }
    }
}

exports.update_filters_view = function () {
    const rendered_filters = render_recent_topics_filters({
        filter_participated: filters.has("participated"),
        filter_unread: filters.has("unread"),
        filter_muted: filters.has("include_muted"),
    });
    $("#recent_filters_group").html(rendered_filters);
    show_selected_filters();

    topics_widget.hard_redraw();
    revive_current_focus();
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
    // Prepare header
    const rendered_body = render_recent_topics_body({
        filter_participated: filters.has("participated"),
        filter_unread: filters.has("unread"),
        filter_muted: filters.has("include_muted"),
        search_val: $("#recent_topics_search").val() || "",
    });
    $("#recent_topics_table").html(rendered_body);
    show_selected_filters();

    // Show topics list
    const container = $(".recent_topics_table table tbody");
    container.empty();
    const mapped_topic_values = Array.from(exports.get().values()).map((value) => value);

    topics_widget = list_render.create(container, mapped_topic_values, {
        name: "recent_topics_table",
        parent_container: $("#recent_topics_table"),
        modifier(item) {
            return render_recent_topic_row(format_topic(item));
        },
        filter: {
            // We use update_filters_view & filters_should_hide_topic to do all the
            // filtering for us, which is called using click_handlers.
            predicate(topic_data) {
                return !exports.filters_should_hide_topic(topic_data);
            },
        },
        sort_fields: {
            stream_sort,
            topic_sort,
        },
        html_selector: get_topic_row,
        simplebar_container: $("#recent_topics_table .table_fix_head"),
    });
    revive_current_focus();
};

exports.launch = function () {
    overlays.open_overlay({
        name: "recent_topics",
        overlay: $("#recent_topics_overlay"),
        on_close() {
            hashchange.exit_overlay();
        },
    });
    exports.complete_rerender();
};

function filter_buttons() {
    return $("#recent_filters_group").children();
}

exports.change_focused_element = function (e, input_key) {
    // Called from hotkeys.js; like all logic in that module,
    // returning true will cause the caller to do
    // preventDefault/stopPropagation; false will let the browser
    // handle the key.
    const $elem = $(e.target);

    if ($("#recent_topics_table").find(":focus").length === 0) {
        // This is a failsafe to return focus back to recent topics overlay,
        // in case it loses focus due to some unknown reason.
        set_default_focus();
        return false;
    }

    if (e.target.id === "recent_topics_search") {
        // Since the search box a text area, we want the browser to handle
        // Left/Right and selection within the widget; but if the user
        // arrows off the edges, we should move focus to the adjacent widgets..
        const textInput = $("#recent_topics_search").get(0);
        const start = textInput.selectionStart;
        const end = textInput.selectionEnd;
        const text_length = textInput.value.length;
        let is_selected = false;
        if (end - start > 0) {
            is_selected = true;
        }

        switch (input_key) {
            case "vim_left":
            case "vim_right":
            case "vim_down":
            case "vim_up":
                return false;
            case "shift_tab":
                current_focus_elem = filter_buttons().last();
                break;
            case "left_arrow":
                if (start !== 0 || is_selected) {
                    return false;
                }
                current_focus_elem = filter_buttons().last();
                break;
            case "tab":
                current_focus_elem = filter_buttons().first();
                break;
            case "right_arrow":
                if (end !== text_length || is_selected) {
                    return false;
                }
                current_focus_elem = filter_buttons().first();
                break;
            case "down_arrow":
                set_table_focus(row_focus, col_focus);
                return true;
            case "click":
                // Note: current_focus_elem can be different here, so we just
                // set current_focus_elem to the input box, we don't want .trigger("focus") on
                // it since it is already focused.
                // We only do this for search because we don't want the focus to
                // go away from the input box when `revive_current_focus` is called
                // on rerender when user is typing.
                current_focus_elem = $("#recent_topics_search");
                return true;
        }
    } else if ($elem.hasClass("btn-recent-filters")) {
        switch (input_key) {
            case "shift_tab":
            case "vim_left":
            case "left_arrow":
                if (filter_buttons().first()[0] === $elem[0]) {
                    current_focus_elem = $("#recent_topics_search");
                } else {
                    current_focus_elem = $elem.prev();
                }
                break;
            case "tab":
            case "vim_right":
            case "right_arrow":
                if (filter_buttons().last()[0] === $elem[0]) {
                    current_focus_elem = $("#recent_topics_search");
                } else {
                    current_focus_elem = $elem.next();
                }
                break;
            case "vim_down":
            case "down_arrow":
                set_table_focus(row_focus, col_focus);
                return true;
        }
    } else if (current_focus_elem === "table") {
        // For arrowing around the table of topics, we implement left/right
        // wraparound.  Going off the top or the bottom takes one
        // to the navigation at the top (see set_table_focus).
        switch (input_key) {
            case "shift_tab":
            case "vim_left":
            case "left_arrow":
                col_focus -= 1;
                if (col_focus < 0) {
                    col_focus = MAX_SELECTABLE_COLS - 1;
                }
                break;
            case "tab":
            case "vim_right":
            case "right_arrow":
                col_focus += 1;
                if (col_focus >= MAX_SELECTABLE_COLS) {
                    col_focus = 0;
                }
                break;
            case "vim_down":
            case "down_arrow":
                row_focus += 1;
                break;
            case "vim_up":
            case "up_arrow":
                row_focus -= 1;
        }
        set_table_focus(row_focus, col_focus);
        return true;
    }
    if (current_focus_elem) {
        current_focus_elem.trigger("focus");
    }

    return true;
};

window.recent_topics = exports;
