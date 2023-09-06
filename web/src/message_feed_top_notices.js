import $ from "jquery";

import * as hash_util from "./hash_util";
import * as message_lists from "./message_lists";
import * as narrow_banner from "./narrow_banner";
import * as narrow_state from "./narrow_state";

function show_history_limit_notice() {
    $(".top-messages-logo").hide();
    $(".history-limited-box").show();
    narrow_banner.hide_empty_narrow_message();
}

function hide_history_limit_notice() {
    $(".top-messages-logo").show();
    $(".history-limited-box").hide();
}

function hide_end_of_results_notice() {
    $(".all-messages-search-caution").hide();
}

function show_end_of_results_notice() {
    $(".all-messages-search-caution").show();

    // Set the link to point to this search with streams:public added.
    // Note that element we adjust is not visible to spectators.
    const operators = narrow_state.filter().operators();
    const update_hash = hash_util.search_public_streams_notice_url(operators);
    $(".all-messages-search-caution a.search-shared-history").attr("href", update_hash);
}

export function update_top_of_narrow_notices(msg_list) {
    // Assumes that the current state is all notices hidden (i.e. this
    // will not hide a notice that should not be there)
    if (msg_list !== message_lists.current) {
        return;
    }

    if (
        msg_list.data.fetch_status.has_found_oldest() &&
        message_lists.current !== message_lists.home
    ) {
        const filter = narrow_state.filter();
        if (filter === undefined && !narrow_state.is_message_feed_visible()) {
            // user moved away from the narrow / filter to Recent Conversations.
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
            show_end_of_results_notice();
        }
    }

    if (msg_list.data.fetch_status.history_limited()) {
        show_history_limit_notice();
    }
}

export function hide_top_of_narrow_notices() {
    hide_end_of_results_notice();
    hide_history_limit_notice();
}
