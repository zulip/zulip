import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import * as channel_folders from "./channel_folders.ts";
import type {Filter} from "./filter.ts";
import {localstorage} from "./localstorage.ts";
import * as message_reminder from "./message_reminder.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as resize from "./resize.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as stream_list_sort from "./stream_list_sort.ts";
import * as sub_store from "./sub_store.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import {user_settings} from "./user_settings.ts";

let last_mention_count = 0;
const ls_key = "left_sidebar_views_state";
const ls = localstorage();

const STATES = {
    EXPANDED: "expanded",
    CONDENSED: "condensed",
};

function restore_views_state(): void {
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

function save_state(state: string): void {
    ls.set(ls_key, state);
}

export function update_starred_count(count: number, hidden: boolean): void {
    const $starred_li = $(".top_left_starred_messages");
    ui_util.update_unread_count_in_dom($starred_li, count);

    if (hidden) {
        $starred_li.addClass("hide_starred_message_count");
        return;
    }
    $starred_li.removeClass("hide_starred_message_count");
}

export function update_scheduled_messages_row(): void {
    const $scheduled_li = $(".top_left_scheduled_messages");
    const count = scheduled_messages.get_count();
    if (count > 0) {
        $scheduled_li.addClass("show-with-scheduled-messages");
    } else {
        $scheduled_li.removeClass("show-with-scheduled-messages");
    }
    ui_util.update_unread_count_in_dom($scheduled_li, count);
}

export function update_reminders_row(): void {
    const $reminders_li = $(".top_left_reminders");
    const count = message_reminder.get_count();
    if (count > 0) {
        $reminders_li.addClass("show-with-reminders");
    } else {
        $reminders_li.removeClass("show-with-reminders");
    }
    ui_util.update_unread_count_in_dom($reminders_li, count);
}

function should_mask_unread_count(showing_muted: boolean): boolean {
    if (!user_settings.web_left_sidebar_unreads_count_summary) {
        return true;
    }
    if (settings_data.should_mask_unread_count(false)) {
        return true;
    }
    if (showing_muted && settings_data.should_mask_unread_count(true)) {
        return true;
    }
    return false;
}

export function update_dom_with_unread_counts(
    counts: unread.FullUnreadCountsData,
    skip_animations: boolean,
): void {
    // Note that direct message counts are handled in pm_list.ts.

    // mentioned/home views have simple integer counts
    const $mentioned_li = $(".top_left_mentions");
    const $home_view_li = $(".selected-home-view");
    const $back_to_streams = $("#topics_header");

    ui_util.update_unread_count_in_dom($mentioned_li, counts.mentioned_message_count);
    ui_util.update_unread_count_in_dom($home_view_li, counts.home_unread_messages);
    ui_util.update_unread_count_in_dom($back_to_streams, counts.stream_unread_messages);

    // TODO(evy) Make some data structures to clean up this function a bit.
    let pinned_unmuted_unread_count = 0;
    let pinned_muted_unread_count = 0;
    const folder_unmuted_unread_counts = new Map<number, number>();
    const folder_muted_unread_counts = new Map<number, number>();
    // These are used for the "+ n inactive channels" button
    const folder_inactive_muted_unread_counts = new Map<number, number>();
    const folder_inactive_unmuted_unread_counts = new Map<number, number>();
    let normal_unmuted_unread_count = 0;
    let normal_muted_unread_count = 0;
    let inactive_unmuted_unread_count = 0;
    let inactive_muted_unread_count = 0;

    for (const [stream_id, stream_count_info] of counts.stream_count.entries()) {
        const sub = sub_store.get(stream_id);
        assert(sub);
        if (sub.pin_to_top) {
            pinned_unmuted_unread_count += stream_count_info.unmuted_count;
            pinned_muted_unread_count += stream_count_info.muted_count;
        } else if (sub.folder_id !== null) {
            const prev_unmuted_count = folder_unmuted_unread_counts.get(sub.folder_id) ?? 0;
            folder_unmuted_unread_counts.set(
                sub.folder_id,
                prev_unmuted_count + stream_count_info.unmuted_count,
            );
            const prev_muted_count = folder_muted_unread_counts.get(sub.folder_id) ?? 0;
            folder_muted_unread_counts.set(
                sub.folder_id,
                prev_muted_count + stream_count_info.muted_count,
            );

            if (!stream_list_sort.has_recent_activity(sub)) {
                const prev_muted_inactive_count =
                    folder_inactive_muted_unread_counts.get(sub.folder_id) ?? 0;
                folder_inactive_muted_unread_counts.set(
                    sub.folder_id,
                    prev_muted_inactive_count + stream_count_info.muted_count,
                );
                const prev_unmuted_inactive_count =
                    folder_inactive_unmuted_unread_counts.get(sub.folder_id) ?? 0;
                folder_inactive_unmuted_unread_counts.set(
                    sub.folder_id,
                    prev_unmuted_inactive_count + stream_count_info.unmuted_count,
                );
            }
        } else if (stream_list_sort.has_recent_activity(sub)) {
            normal_unmuted_unread_count += stream_count_info.unmuted_count;
            normal_muted_unread_count += stream_count_info.muted_count;
        } else {
            inactive_unmuted_unread_count += stream_count_info.unmuted_count;
            inactive_muted_unread_count += stream_count_info.muted_count;
        }
    }

    function update_section_unread_count(
        $unread_elem: JQuery,
        unmuted_count: number,
        muted_count: number,
    ): void {
        const show_muted_count = unmuted_count === 0 && muted_count > 0;
        if (show_muted_count) {
            ui_util.update_unread_count_in_dom($unread_elem, muted_count);
        } else {
            ui_util.update_unread_count_in_dom($unread_elem, unmuted_count);
        }
        $unread_elem.toggleClass("muted_count", show_muted_count);
        $unread_elem.toggleClass(
            "hide-unread-messages-count",
            should_mask_unread_count(show_muted_count),
        );
    }
    update_section_unread_count(
        $("#stream-list-pinned-streams-container .stream-list-subsection-header"),
        pinned_unmuted_unread_count,
        pinned_muted_unread_count,
    );
    update_section_unread_count(
        $("#stream-list-normal-streams-container .stream-list-subsection-header"),
        normal_unmuted_unread_count,
        normal_muted_unread_count,
    );
    update_section_unread_count(
        $("#stream-list-dormant-streams-container .stream-list-subsection-header"),
        inactive_unmuted_unread_count,
        inactive_muted_unread_count,
    );

    for (const folder_id of channel_folders.get_channel_ids()) {
        update_section_unread_count(
            $(`#stream-list-${folder_id}-container .stream-list-subsection-header`),
            folder_unmuted_unread_counts.get(folder_id) ?? 0,
            folder_muted_unread_counts.get(folder_id) ?? 0,
        );
        update_section_unread_count(
            $(`#stream-list-${folder_id}-container .show-inactive-channels`),
            folder_inactive_unmuted_unread_counts.get(folder_id) ?? 0,
            folder_inactive_muted_unread_counts.get(folder_id) ?? 0,
        );
    }

    if (!skip_animations) {
        animate_mention_changes($mentioned_li, counts.mentioned_message_count);
    }
}

export let select_top_left_corner_item = function (narrow_to_activate: string): void {
    $(".top-left-active-filter").removeClass("top-left-active-filter");
    if (narrow_to_activate !== "") {
        $(narrow_to_activate).addClass("top-left-active-filter");
    }
};

export function rewire_select_top_left_corner_item(
    func: (narrow_to_activate: string) => void,
): void {
    select_top_left_corner_item = func;
}

export function handle_narrow_activated(filter: Filter): void {
    let ops: string[];
    let filter_name: string;

    // TODO: handle confused filters like "in:all stream:foo"
    ops = filter.operands("in");
    if (ops[0] !== undefined) {
        filter_name = ops[0];
        if (filter_name === "home") {
            highlight_all_messages_view();
            return;
        }
    }
    ops = filter.operands("is");
    if (ops[0] !== undefined) {
        filter_name = ops[0];
        if (filter_name === "starred") {
            select_top_left_corner_item(".top_left_starred_messages");
            return;
        } else if (filter_name === "mentioned") {
            select_top_left_corner_item(".top_left_mentions");
            return;
        }
    }
    const term_types = filter.sorted_term_types();
    if (
        _.isEqual(term_types, ["sender", "has-reaction"]) &&
        filter.operands("sender")[0] === people.my_current_email()
    ) {
        select_top_left_corner_item(".top_left_my_reactions");
        return;
    }

    // If we don't have a specific handler for this narrow, we just clear all.
    select_top_left_corner_item("");
}

function toggle_condensed_navigation_area(): void {
    const $views_label_container = $("#views-label-container");
    const $views_label_icon = $("#toggle-top-left-navigation-area-icon");

    if (page_params.is_spectator) {
        // We don't support collapsing VIEWS for spectators, so exit early.
        return;
    }

    if ($views_label_container.hasClass("showing-expanded-navigation")) {
        // Toggle into the condensed state
        $views_label_container.addClass("showing-condensed-navigation");
        $views_label_container.removeClass("showing-expanded-navigation");
        $views_label_icon.addClass("rotate-icon-right");
        $views_label_icon.removeClass("rotate-icon-down");
        save_state(STATES.CONDENSED);
    } else {
        // Toggle into the expanded state
        $views_label_container.addClass("showing-expanded-navigation");
        $views_label_container.removeClass("showing-condensed-navigation");
        $views_label_icon.addClass("rotate-icon-down");
        $views_label_icon.removeClass("rotate-icon-right");
        save_state(STATES.EXPANDED);
    }
    resize.resize_stream_filters_container();
}

export function animate_mention_changes($li: JQuery, new_mention_count: number): void {
    if (new_mention_count > last_mention_count) {
        do_new_messages_animation($li);
    }
    last_mention_count = new_mention_count;
}

function do_new_messages_animation($li: JQuery): void {
    $li.addClass("new_messages");
    function mid_animation(): void {
        $li.removeClass("new_messages");
        $li.addClass("new_messages_fadeout");
    }
    function end_animation(): void {
        $li.removeClass("new_messages_fadeout");
    }
    setTimeout(mid_animation, 3000);
    setTimeout(end_animation, 6000);
}

export function highlight_inbox_view(): void {
    select_top_left_corner_item(".top_left_inbox");

    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function highlight_recent_view(): void {
    select_top_left_corner_item(".top_left_recent_view");

    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function highlight_all_messages_view(): void {
    select_top_left_corner_item(".top_left_all_messages");

    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function get_view_rows_by_view_name(view: string): JQuery {
    if (view === settings_config.web_home_view_values.all_messages.code) {
        return $(".top_left_all_messages");
    }

    if (view === settings_config.web_home_view_values.recent_topics.code) {
        return $(".top_left_recent_view");
    }

    return $(".top_left_inbox");
}

// Reorder <li> views elements in the DOM based on the current home_view.
// Called twice: on initial page load and when home_view changes.
export function reorder_left_sidebar_navigation_list(home_view: string): void {
    const $left_sidebar = $("#left-sidebar-navigation-list");
    const $left_sidebar_condensed = $("#left-sidebar-navigation-list-condensed");

    // First, re-order the views back to the original default order, to preserve the relative order.
    for (const key of Object.keys(settings_config.web_home_view_values).reverse()) {
        if (key !== home_view) {
            const $view = get_view_rows_by_view_name(key);
            $view.eq(1).prependTo($left_sidebar);
            $view.eq(0).prependTo($left_sidebar_condensed);
        }
    }

    // Detach the selected home_view and inserts it at the beginning of the navigation list.
    const $selected_home_view = get_view_rows_by_view_name(home_view);
    $selected_home_view.eq(1).prependTo($left_sidebar);
    $selected_home_view.eq(0).prependTo($left_sidebar_condensed);
}

export function handle_home_view_changed(new_home_view: string): void {
    const $current_home_view = $(".selected-home-view");
    const $new_home_view = get_view_rows_by_view_name(new_home_view);
    const res = unread.get_counts();

    // Remove class from current home view
    $current_home_view.removeClass("selected-home-view");

    // Add the class to the matching home view
    $new_home_view.addClass("selected-home-view");

    reorder_left_sidebar_navigation_list(new_home_view);
    update_dom_with_unread_counts(res, true);
}

export function initialize(): void {
    update_reminders_row();
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
