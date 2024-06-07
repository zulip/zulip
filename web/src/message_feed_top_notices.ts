import $ from "jquery";
import assert from "minimalistic-assert";

import * as hash_util from "./hash_util";
import * as message_lists from "./message_lists";
import type {MessageList} from "./message_lists";
import * as narrow_banner from "./narrow_banner";
import * as narrow_state from "./narrow_state";

const show_history_limit_notice = (): void => {
    $(".top-messages-logo").hide();
    $(".history-limited-box").show();
    narrow_banner.hide_empty_narrow_message();
};

const hide_history_limit_notice = (): void => {
    $(".top-messages-logo").show();
    $(".history-limited-box").hide();
};

const hide_end_of_results_notice = (): void => {
    $(".all-messages-search-caution").hide();
};

const show_end_of_results_notice = (): void => {
    $(".all-messages-search-caution").show();

    // Set the link to point to this search with streams:public added.
    // Note that element we adjust is not visible to spectators.
    const narrow_filter = narrow_state.filter();
    assert(narrow_filter !== undefined);
    const terms = narrow_filter.terms();
    const update_hash = hash_util.search_public_streams_notice_url(terms);
    $(".all-messages-search-caution a.search-shared-history").attr("href", update_hash);
};

export const update_top_of_narrow_notices = (msg_list: MessageList): void => {
    // Assumes that the current state is all notices hidden (i.e. this
    // will not hide a notice that should not be there)
    if (message_lists.current === undefined || msg_list !== message_lists.current) {
        return;
    }

    if (msg_list.data.fetch_status.has_found_oldest()) {
        const filter = narrow_state.filter();
        // Potentially display the notice that lets users know
        // that not all messages were searched.  One could
        // imagine including `filter.is_keyword_search()` in these
        // conditions, but there's a very legitimate use case
        // for moderation of searching for all messages sent
        // by a potential spammer user.
        if (
            filter &&
            !filter.is_in_home() &&
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
};

export const hide_top_of_narrow_notices = (): void => {
    hide_end_of_results_notice();
    hide_history_limit_notice();
};
