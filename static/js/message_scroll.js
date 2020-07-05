"use strict";

const _ = require("lodash");

let actively_scrolling = false;

// Tracks whether the next scroll that will complete is initiated by
// code, not the user, and thus should avoid moving the selected
// message.
let update_selection_on_next_scroll = true;
exports.suppress_selection_update_on_next_scroll = function () {
    update_selection_on_next_scroll = false;
};

let loading_older_messages_indicator_showing = false;
let loading_newer_messages_indicator_showing = false;
exports.show_loading_older = function () {
    if (!loading_older_messages_indicator_showing) {
        loading.make_indicator($("#loading_older_messages_indicator"), {abs_positioned: true});
        loading_older_messages_indicator_showing = true;
        floating_recipient_bar.hide();
    }
};

exports.hide_loading_older = function () {
    if (loading_older_messages_indicator_showing) {
        loading.destroy_indicator($("#loading_older_messages_indicator"));
        loading_older_messages_indicator_showing = false;
    }
};

exports.show_loading_newer = function () {
    if (!loading_newer_messages_indicator_showing) {
        $(".bottom-messages-logo").show();
        loading.make_indicator($("#loading_newer_messages_indicator"), {abs_positioned: true});
        loading_newer_messages_indicator_showing = true;
        floating_recipient_bar.hide();
    }
};

exports.hide_loading_newer = function () {
    if (loading_newer_messages_indicator_showing) {
        $(".bottom-messages-logo").hide();
        loading.destroy_indicator($("#loading_newer_messages_indicator"));
        loading_newer_messages_indicator_showing = false;
    }
};

exports.hide_indicators = function () {
    exports.hide_loading_older();
    exports.hide_loading_newer();
};

exports.show_history_limit_notice = function () {
    $(".top-messages-logo").hide();
    $(".history-limited-box").show();
    narrow.hide_empty_narrow_message();
};

exports.hide_history_limit_notice = function () {
    $(".top-messages-logo").show();
    $(".history-limited-box").hide();
};

exports.hide_end_of_results_notice = function () {
    $(".all-messages-search-caution").hide();
};

exports.show_end_of_results_notice = function () {
    $(".all-messages-search-caution").show();
    // Set the link to point to this search with streams:public added.
    // It's a bit hacky to use the href, but
    // !filter.includes_full_stream_history() implies streams:public
    // wasn't already present.
    const update_hash = hash_util.search_public_streams_notice_url();
    $(".all-messages-search-caution a.search-shared-history").attr("href", update_hash);
};

exports.update_top_of_narrow_notices = function (msg_list) {
    // Assumes that the current state is all notices hidden (i.e. this
    // will not hide a notice that should not be there)
    if (msg_list !== current_msg_list) {
        return;
    }

    if (msg_list.data.fetch_status.has_found_oldest() && current_msg_list !== home_msg_list) {
        const filter = narrow_state.filter();
        if (filter === undefined && recent_topics.is_visible()) {
            // user moved away from the narrow / filter to recent topics.
            return;
        }
        // Potentially display the notice that lets users know
        // that not all messages were searched.  One could
        // imagine including `filter.is_search()` in these
        // conditions, but there's a very legitimate use case
        // for moderation of searching for all messages sent
        // by a potential spammer user.
        if (
            !filter.contains_only_private_messages() &&
            !filter.includes_full_stream_history() &&
            !filter.is_personal_filter()
        ) {
            exports.show_end_of_results_notice();
        }
    }

    if (msg_list.data.fetch_status.history_limited()) {
        exports.show_history_limit_notice();
    }
};

exports.hide_top_of_narrow_notices = function () {
    exports.hide_end_of_results_notice();
    exports.hide_history_limit_notice();
};

exports.is_actively_scrolling = function () {
    return actively_scrolling;
};

exports.scroll_finished = function () {
    actively_scrolling = false;

    if (!$("#message_feed_container").hasClass("active")) {
        return;
    }

    if (update_selection_on_next_scroll) {
        message_viewport.keep_pointer_in_view();
    } else {
        update_selection_on_next_scroll = true;
    }

    floating_recipient_bar.update();

    if (message_viewport.at_top()) {
        message_fetch.maybe_load_older_messages({
            msg_list: current_msg_list,
        });
    }

    if (message_viewport.at_bottom()) {
        message_fetch.maybe_load_newer_messages({
            msg_list: current_msg_list,
        });
    }

    // When the window scrolls, it may cause some messages to
    // enter the screen and become read.  Calling
    // unread_ops.process_visible will update necessary
    // data structures and DOM elements.
    setTimeout(unread_ops.process_visible, 0);
};

let scroll_timer;
function scroll_finish() {
    actively_scrolling = true;
    clearTimeout(scroll_timer);
    scroll_timer = setTimeout(exports.scroll_finished, 100);
}

exports.initialize = function () {
    message_viewport.message_pane.on(
        "scroll",
        _.throttle(() => {
            unread_ops.process_visible();
            scroll_finish();
        }, 50),
    );

    // Scroll handler that marks messages as read when you scroll past them.
    $(document).on("message_selected.zulip", (event) => {
        if (event.id === -1) {
            return;
        }

        if (event.mark_read && event.previously_selected_id !== -1) {
            // Mark messages between old pointer and new pointer as read
            let messages;
            if (event.id < event.previously_selected_id) {
                messages = event.msg_list.message_range(event.id, event.previously_selected_id);
            } else {
                messages = event.msg_list.message_range(event.previously_selected_id, event.id);
            }
            if (event.msg_list.can_mark_messages_read()) {
                unread_ops.notify_server_messages_read(messages, {from: "pointer"});
            }
        }
    });
};

window.message_scroll = exports;
