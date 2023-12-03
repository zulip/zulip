import $ from "jquery";

import {localstorage} from "./localstorage";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as resize from "./resize";
import * as scheduled_messages from "./scheduled_messages";
import * as settings_config from "./settings_config";
import * as ui_util from "./ui_util";
import * as unread from "./unread";

let last_mention_count = 0;
const ls_key = "left_sidebar_views_state";
const ls = localstorage();

const STATES = {
    EXPANDED: "expanded",
    CONDENSED: "condensed",
};

function restore_views_state() {
    if (page_params.is_spectator) {
        // Spectators should always see the expanded view.
        return;
    }

    const views_state = ls.get(ls_key);
    // Expanded state is default, so we only need to toggle if the state is condensed.
    if (views_state === STATES.CONDENSED) {
        toggle_condensed_navigation_area();
    }
}

function save_state(state) {
    ls.set(ls_key, state);
}

export function update_starred_count(count) {
    const $starred_li = $(".top_left_starred_messages");
    ui_util.update_unread_count_in_dom($starred_li, count);
}

export function update_scheduled_messages_row() {
    const $scheduled_li = $(".top_left_scheduled_messages");
    const count = scheduled_messages.get_count();
    if (count > 0) {
        $scheduled_li.addClass("show-with-scheduled-messages");
    } else {
        $scheduled_li.removeClass("show-with-scheduled-messages");
    }
    ui_util.update_unread_count_in_dom($scheduled_li, count);
}

export function update_dom_with_unread_counts(counts, skip_animations) {
    // Note that direct message counts are handled in pm_list.js.

    // mentioned/home views have simple integer counts
    const $mentioned_li = $(".top_left_mentions");
    const $home_view_li = $(".selected-home-view");
    const $streams_header = $("#streams_header");
    const $back_to_streams = $("#topics_header");

    ui_util.update_unread_count_in_dom($mentioned_li, counts.mentioned_message_count);
    ui_util.update_unread_count_in_dom($home_view_li, counts.home_unread_messages);
    ui_util.update_unread_count_in_dom($streams_header, counts.stream_unread_messages);
    ui_util.update_unread_count_in_dom($back_to_streams, counts.stream_unread_messages);

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
            highlight_all_messages_view();
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

function toggle_condensed_navigation_area() {
    const $views_label_container = $("#views-label-container");
    const $views_label_icon = $("#toggle-top-left-navigation-area-icon");
    if ($views_label_container.hasClass("showing-expanded-navigation")) {
        // Toggle into the condensed state
        $views_label_container.addClass("showing-condensed-navigation");
        $views_label_container.removeClass("showing-expanded-navigation");
        $views_label_icon.addClass("fa-caret-right");
        $views_label_icon.removeClass("fa-caret-down");
        save_state(STATES.CONDENSED);
    } else {
        // Toggle into the expanded state
        $views_label_container.addClass("showing-expanded-navigation");
        $views_label_container.removeClass("showing-condensed-navigation");
        $views_label_icon.addClass("fa-caret-down");
        $views_label_icon.removeClass("fa-caret-right");
        save_state(STATES.EXPANDED);
    }
    resize.resize_stream_filters_container();
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

export function highlight_inbox_view() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_recent_view"));
    remove($(".top_left_mentions"));
    narrow_state.reset_current_filter();
    $(".top_left_inbox").addClass("active-filter");
    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function highlight_recent_view() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_inbox"));
    narrow_state.reset_current_filter();
    $(".top_left_recent_view").addClass("active-filter");
    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function highlight_all_messages_view() {
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_recent_view"));
    remove($(".top_left_inbox"));
    $(".top_left_all_messages").addClass("active-filter");
    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

function handle_home_view_order(home_view) {
    // Remove class and tabindex from current home view
    const $current_home_view = $(".selected-home-view");
    $current_home_view.removeAttr("tabindex");
    $current_home_view.removeClass("selected-home-view");

    const $all_messages_rows = $(".top_left_all_messages");
    const $recent_views_rows = $(".top_left_recent_view");
    const $inbox_rows = $(".top_left_inbox");

    const res = unread.get_counts();

    // Add the class and tabindex to the matching home view
    if (home_view === settings_config.web_home_view_values.all_messages.code) {
        $all_messages_rows.addClass("selected-home-view");
        $all_messages_rows.find("a").attr("tabindex", 0);
    } else if (home_view === settings_config.web_home_view_values.recent_topics.code) {
        $recent_views_rows.addClass("selected-home-view");
        $recent_views_rows.find("a").attr("tabindex", 0);
    } else {
        // Inbox is home view.
        $inbox_rows.addClass("selected-home-view");
        $inbox_rows.find("a").attr("tabindex", 0);
    }
    update_dom_with_unread_counts(res, true);
}

export function handle_home_view_changed(new_home_view) {
    const $recent_view_sidebar_menu_icon = $(".recent-view-sidebar-menu-icon");
    const $all_messages_sidebar_menu_icon = $(".all-messages-sidebar-menu-icon");
    if (new_home_view === settings_config.web_home_view_values.all_messages.code) {
        $recent_view_sidebar_menu_icon.removeClass("hide");
        $all_messages_sidebar_menu_icon.addClass("hide");
    } else if (new_home_view === settings_config.web_home_view_values.recent_topics.code) {
        $recent_view_sidebar_menu_icon.addClass("hide");
        $all_messages_sidebar_menu_icon.removeClass("hide");
    } else {
        // Inbox is home view.
        $recent_view_sidebar_menu_icon.removeClass("hide");
        $all_messages_sidebar_menu_icon.removeClass("hide");
    }
    handle_home_view_order(new_home_view);
}

export function initialize() {
    update_scheduled_messages_row();
    restore_views_state();

    $("body").on(
        "click",
        "#toggle-top-left-navigation-area-icon, #views-label-container .left-sidebar-title",
        (e) => {
            e.stopPropagation();
            toggle_condensed_navigation_area();
        },
    );
}
