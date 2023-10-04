import $ from "jquery";

import render_active_view_row from "../templates/active_view_row.hbs";

import * as pm_list from "./pm_list";
import * as resize from "./resize";
import * as scheduled_messages from "./scheduled_messages";
import * as starred_messages from "./starred_messages";
import * as ui_util from "./ui_util";
import * as unread from "./unread";

let last_mention_count = 0;
let left_sidebar_navigation_area_expanded = true;
const views_data = {
    all_messages: {
        active_view_name: "all_messages",
        active_view_url: "#all_messages",
        active_view_tooltip: "all-message-tooltip-template",
        active_view_icon: "fa fa-align-left",
        active_view_label: "All messages",
        active_view_sidebar_menu_icon: "all-messages-sidebar-menu-icon",
    },
    inbox: {
        active_view_name: "inbox",
        active_view_url: "#inbox",
        active_view_tooltip: "inbox-tooltip-template",
        active_view_icon: "zulip-icon zulip-icon-inbox",
        active_view_label: "Inbox",
    },
    recent_view: {
        active_view_name: "recent_view",
        active_view_url: "#recent",
        active_view_tooltip: "recent-conversations-tooltip-template",
        active_view_icon: "fa fa-clock-o",
        active_view_label: "Recent conversations",
    },
    mentions: {
        active_view_name: "mentions",
        active_view_url: "#narrow/is/mentioned",
        active_view_icon: "fa fa-at",
        active_view_label: "Mentions",
    },
    starred_messages: {
        active_view_name: "starred_messages",
        active_view_url: "#narrow/is/starred",
        active_view_icon: "zulip-icon zulip-icon-star-filled",
        active_view_label: "Starred messages",
        active_view_sidebar_menu_icon: "starred-messages-sidebar-menu-icon",
    },
};

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
    $(".active-view-row").empty();
}

export function deselect_top_left_corner_items() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_recent_view"));
    remove($(".top_left_inbox"));
}

function expand() {
    $("#toggle-top-left-navigation-area-icon").addClass("fa-caret-down");
    $("#toggle-top-left-navigation-area-icon").removeClass("fa-caret-right");

    $(".left-sidebar-navigation-area").removeClass("collapsed");
}

function close() {
    $("#toggle-top-left-navigation-area-icon").removeClass("fa-caret-down");
    $("#toggle-top-left-navigation-area-icon").addClass("fa-caret-right");

    $(".left-sidebar-navigation-area").addClass("collapsed");
}

export function toggle_top_left_navigation_area() {
    if (left_sidebar_navigation_area_expanded) {
        close();
        left_sidebar_navigation_area_expanded = false;
    } else {
        expand();
        left_sidebar_navigation_area_expanded = true;
    }
    pm_list.update_private_messages();
}

function set_active_view_row(active_view_name) {
    const active_view_data = views_data[active_view_name];
    $(".active-view-row").html(render_active_view_row(active_view_data));

    if (active_view_name === "all_messages" || active_view_name === "mentions") {
        update_dom_with_unread_counts(unread.get_counts(), true);
    } else if (active_view_name === "starred_messages") {
        update_starred_count(starred_messages.get_count());
    }
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
            set_active_view_row("all_messages");
        }
    }
    ops = filter.operands("is");
    if (ops.length >= 1) {
        filter_name = ops[0];
        if (filter_name === "starred") {
            $filter_li = $(".top_left_starred_messages");
            $filter_li.addClass("active-filter");
            set_active_view_row("starred_messages");
        } else if (filter_name === "mentioned") {
            $filter_li = $(".top_left_mentions");
            $filter_li.addClass("active-filter");
            set_active_view_row("mentions");
        }
    }
}

export function handle_narrow_deactivated() {
    deselect_top_left_corner_items();

    const $filter_li = $(".top_left_all_messages");
    $filter_li.addClass("active-filter");
    set_active_view_row("all_messages");
}

export function highlight_recent_view() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_mentions"));
    remove($(".top_left_inbox"));
    $(".top_left_recent_view").addClass("active-filter");
    set_active_view_row("recent_view");
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

    $("body").on(
        "keydown",
        "#left-sidebar-navigation-area #views-label-container",
        ui_util.convert_enter_to_click,
    );
}

export function highlight_inbox_view() {
    remove($(".top_left_all_messages"));
    remove($(".top_left_starred_messages"));
    remove($(".top_left_recent_view"));
    remove($(".top_left_mentions"));
    $(".top_left_inbox").addClass("active-filter");
    set_active_view_row("inbox");
    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}
