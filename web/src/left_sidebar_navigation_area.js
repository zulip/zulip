import $ from "jquery";

import * as resize from "./resize";
import * as scheduled_messages from "./scheduled_messages";
import * as ui_util from "./ui_util";

let last_mention_count = 0;

export function update_starred_count(count) {
    const $starred_li = $(".top_left_starred_messages");
    ui_util.update_unread_count_in_dom($starred_li, count);
}

export function update_scheduled_messages_row() {
    const $scheduled_li = $(".top_left_scheduled_messages");
    const count = scheduled_messages.get_count();
    if (count > 0) {
        $scheduled_li.show();
    } else {
        $scheduled_li.hide();
    }
    ui_util.update_unread_count_in_dom($scheduled_li, count);
}

export function update_dom_with_unread_counts(counts, skip_animations) {
    // Note that direct message counts are handled in pm_list.js.

    // mentioned/home have simple integer counts
    const $mentioned_li = $(".top_left_mentions");
    const $home_li = $(".top_left_all_messages");

    ui_util.update_unread_count_in_dom($mentioned_li, counts.mentioned_message_count);
    ui_util.update_unread_count_in_dom($home_li, counts.home_unread_messages);

    if (!skip_animations) {
        animate_mention_changes($mentioned_li, counts.mentioned_message_count);
    }
}

// TODO: Rewrite how we handle activation of narrows when doing the redesign.
// We don't want to adjust class for all the buttons when switching narrows.

function remove($elem) {
    $elem.removeClass("active-filter active-sub-filter");
}

export function deselect_top_left_corner_items() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_recent_view"));
    remove($(".top_left_inbox"));
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

export function highlight_recent_view() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_inbox"));
    $(".top_left_recent_view").addClass("active-filter");
    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function animate_mention_changes($li, new_mention_count) {
    if (new_mention_count > last_mention_count) {
        do_new_messages_animation($li);
    }
    last_mention_count = new_mention_count;
}

function do_new_messages_animation($li) {
    $li.addClass("new_messages");
    function mid_animation() {
        $li.removeClass("new_messages");
        $li.addClass("new_messages_fadeout");
    }
    function end_animation() {
        $li.removeClass("new_messages_fadeout");
    }
    setTimeout(mid_animation, 3000);
    setTimeout(end_animation, 6000);
}

export function initialize() {
    update_scheduled_messages_row();
}

export function highlight_inbox_view() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_recent_view"));
    remove($(".top_left_mentions"));
    $(".top_left_inbox").addClass("active-filter");
    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}
