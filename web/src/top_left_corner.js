import $ from "jquery";

import * as resize from "./resize";
import * as ui_util from "./ui_util";
import * as unread_ui from "./unread_ui";

export function update_starred_count(count) {
    const $starred_li = $(".top_left_starred_messages");
    ui_util.update_unread_count_in_dom($starred_li, count);
}

export function update_dom_with_unread_counts(counts) {
    // Note that "Private messages" counts are handled in pm_list.js.

    // mentioned/home have simple integer counts
    const $mentioned_li = $(".top_left_mentions");
    const $home_li = $(".top_left_all_messages");

    ui_util.update_unread_count_in_dom($mentioned_li, counts.mentioned_message_count);
    ui_util.update_unread_count_in_dom($home_li, counts.home_unread_messages);

    unread_ui.animate_mention_changes($mentioned_li, counts.mentioned_message_count);
}

function remove($elem) {
    $elem.removeClass("active-filter active-sub-filter");
}

export function deselect_top_left_corner_items() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_recent_topics"));
}

export function handle_narrow_activated(filter) {
    deselect_top_left_corner_items();

    let ops;
    let filter_name;
    let $filter_li;

    // TODO: handle confused filters like "in:all stream:foo"
    ops = filter.operands("in");
    if (ops.length >= 1) {
        filter_name = ops[0];
        if (filter_name === "home") {
            $filter_li = $(".top_left_all_messages");
            $filter_li.addClass("active-filter");
        }
    }
    ops = filter.operands("is");
    if (ops.length >= 1) {
        filter_name = ops[0];
        if (filter_name === "starred") {
            $filter_li = $(".top_left_starred_messages");
            $filter_li.addClass("active-filter");
        } else if (filter_name === "mentioned") {
            $filter_li = $(".top_left_mentions");
            $filter_li.addClass("active-filter");
        }
    }
}

export function handle_narrow_deactivated() {
    deselect_top_left_corner_items();

    const $filter_li = $(".top_left_all_messages");
    $filter_li.addClass("active-filter");
}

export function narrow_to_recent_topics() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    $(".top_left_recent_topics").addClass("active-filter");
    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}
