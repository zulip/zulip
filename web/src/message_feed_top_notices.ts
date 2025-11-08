import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import * as hash_util from "./hash_util.ts";
import type {MessageList} from "./message_list.ts";
import * as message_lists from "./message_lists.ts";
import * as narrow_banner from "./narrow_banner.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";

function show_history_limit_notice(): void {
    $(".top-messages-logo").hide();
    $(".history-limited-box").show();
    narrow_banner.hide_empty_narrow_message();
}

function hide_history_limit_notice(): void {
    $(".top-messages-logo").show();
    $(".history-limited-box").hide();
}

function hide_end_of_results_notice(): void {
    $(".all-messages-search-caution").hide();
}

function show_end_of_results_notice(): void {
    $(".all-messages-search-caution").show();

    // Set the link to point to this search with streams:public added.
    // Note that element we adjust is not visible to spectators.
    const narrow_filter = narrow_state.filter();
    assert(narrow_filter !== undefined);
    const terms = narrow_filter.terms();
    const update_hash = hash_util.search_public_streams_notice_url(terms);
    $(".all-messages-search-caution a.search-shared-history").attr("href", update_hash);
}

export function update_top_of_narrow_notices(msg_list: MessageList): void {
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
            !filter.is_personal_filter() &&
            !(
                _.isEqual(filter._sorted_term_types, ["sender", "has-reaction"]) &&
                filter.operands("sender")[0] === people.my_current_email()
            )
        ) {
            show_end_of_results_notice();
        }
    }

    if (msg_list.data.fetch_status.history_limited()) {
        show_history_limit_notice();
    }
}

export function hide_top_of_narrow_notices(): void {
    hide_end_of_results_notice();
    hide_history_limit_notice();
}
