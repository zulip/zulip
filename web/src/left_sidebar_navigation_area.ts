import $ from "jquery";
import _ from "lodash";

import render_left_sidebar_expanded_view_items_list from "../templates/left_sidebar_expanded_view_items_list.hbs";
import render_left_sidebar_primary_condensed_view_item from "../templates/left_sidebar_primary_condensed_view_item.hbs";

import * as drafts from "./drafts.ts";
import type {Filter} from "./filter.ts";
import {localstorage} from "./localstorage.ts";
import * as message_reminder from "./message_reminder.ts";
import * as navigation_views from "./navigation_views.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as resize from "./resize.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as settings_config from "./settings_config.ts";
import * as starred_messages from "./starred_messages.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import {user_settings} from "./user_settings.ts";

let last_mention_count = 0;
const ls_key = "left_sidebar_views_state";
const ls = localstorage();
export let current_active_fragment: string | undefined;

const CONDENSED_PRIORITY_SCORE = 2;
const PINNED_VIEW_SCORE = 1;
export const UNPINNED_VIEW_SCORE = 0;
const HIDDEN_VIEW_SCORE = -1;

const STATES = {
    EXPANDED: "expanded",
    CONDENSED: "condensed",
};

export function is_condensed(): boolean {
    return ls.get(ls_key) === STATES.CONDENSED;
}

export function restore_views_state(): void {
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

export function update_drafts_count(): void {
    const $drafts_li = $(".top_left_drafts");
    ui_util.update_unread_count_in_dom($drafts_li, drafts.draft_model.getDraftCount());
}

export function update_scheduled_messages_row(): void {
    const $scheduled_li = $(".top_left_scheduled_messages");
    const count = scheduled_messages.get_count();
    $scheduled_li.toggleClass("hidden-by-filters", count === 0);
    ui_util.update_unread_count_in_dom($scheduled_li, count);
}

export function update_reminders_row(): void {
    const $reminders_li = $(".top_left_reminders");
    const count = message_reminder.get_count();
    $reminders_li.toggleClass("hidden-by-filters", count === 0);
    ui_util.update_unread_count_in_dom($reminders_li, count);
}

export let update_dom_with_unread_counts = function (
    counts: unread.FullUnreadCountsData,
    skip_animations: boolean,
): void {
    // Note that direct message counts are handled in pm_list.ts.

    // mentioned/home views have simple integer counts
    const $mentioned_li = $(".top_left_mentions");
    const $home_view_li = $(".selected-home-view");
    const $condensed_view_li = $(".top_left_condensed_unread_marker");
    const $back_to_streams = $("#topics_header");

    ui_util.update_unread_count_in_dom($mentioned_li, counts.mentioned_message_count);
    ui_util.update_unread_count_in_dom($home_view_li, counts.home_unread_messages);
    ui_util.update_unread_count_in_dom($condensed_view_li, counts.home_unread_messages);
    ui_util.update_unread_count_in_dom($back_to_streams, counts.stream_unread_messages);

    if (!skip_animations) {
        animate_mention_changes($mentioned_li, counts.mentioned_message_count);
    }
};

export function rewire_update_dom_with_unread_counts(
    value: typeof update_dom_with_unread_counts,
): void {
    update_dom_with_unread_counts = value;
}

export let select_top_left_corner_item = function (narrow_to_activate: string): void {
    $(".top-left-active-filter").removeClass("top-left-active-filter");
    if (narrow_to_activate !== "") {
        $(narrow_to_activate).addClass("top-left-active-filter");
        const view_match_key = /\.top_left_(.+)/.exec(narrow_to_activate);

        let fragment;
        if (view_match_key?.[1]) {
            const css_class_suffix = view_match_key[1];
            if (navigation_views.is_built_in_view_key(css_class_suffix)) {
                fragment = navigation_views.built_in_views_meta_data[css_class_suffix].fragment;
            }
        }
        current_active_fragment = fragment;
    } else {
        current_active_fragment = undefined;
    }
    update_sidebar_for_navigation_views();
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

export function expand_views($views_label_container: JQuery, $views_label_icon: JQuery): void {
    $views_label_container.addClass("showing-expanded-navigation");
    $views_label_container.removeClass("showing-condensed-navigation");
    $views_label_icon.addClass("rotate-icon-down");
    $views_label_icon.removeClass("rotate-icon-right");
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
        expand_views($views_label_container, $views_label_icon);
        save_state(STATES.EXPANDED);
    }
    resize.resize_stream_filters_container();
}

export function animate_mention_changes($li: JQuery, new_mention_count: number): void {
    if (new_mention_count > last_mention_count) {
        ui_util.do_new_unread_animation($li);
    }
    last_mention_count = new_mention_count;
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
    for (const key of Object.keys(settings_config.web_home_view_values).toReversed()) {
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

export function get_view_pinned_priority(view: navigation_views.BuiltInViewMetadata): number {
    if (view.fragment === "scheduled" && scheduled_messages.get_count() === 0) {
        return HIDDEN_VIEW_SCORE;
    }
    if (view.fragment === "reminders" && message_reminder.get_count() === 0) {
        return HIDDEN_VIEW_SCORE;
    }
    if (view.prioritize_in_condensed_view && view.is_pinned) {
        return CONDENSED_PRIORITY_SCORE;
    }
    if (view.is_pinned) {
        return PINNED_VIEW_SCORE;
    }
    return UNPINNED_VIEW_SCORE;
}

export function get_primary_condensed_views(): navigation_views.BuiltInViewMetadata[] {
    return navigation_views
        .get_built_in_views()
        .filter((view) => get_view_pinned_priority(view) >= PINNED_VIEW_SCORE)
        .toSorted((a, b) => get_view_pinned_priority(a) - get_view_pinned_priority(b))
        .slice(0, 5);
}

export function get_built_in_pinned_views(
    active_fragment?: string,
): navigation_views.BuiltInViewMetadata[] {
    return navigation_views
        .get_built_in_views()
        .filter(
            (view) =>
                get_view_pinned_priority(view) > 0 ||
                (active_fragment ? view.fragment === active_fragment : false),
        );
}

export function get_built_in_unpinned_views(): navigation_views.BuiltInViewMetadata[] {
    return navigation_views
        .get_built_in_views()
        .filter((view) => get_view_pinned_priority(view) === UNPINNED_VIEW_SCORE);
}

export function get_built_in_views(): navigation_views.BuiltInViewMetadata[] {
    return navigation_views.get_built_in_views();
}

export function update_sidebar_for_navigation_views(): void {
    const primary_condensed_views = get_primary_condensed_views();
    const active_fragment = current_active_fragment;
    const expanded_views = get_built_in_pinned_views(current_active_fragment);
    const active_view = expanded_views.find((view) => view.fragment === active_fragment);
    const has_unpinned_views = get_built_in_unpinned_views().length > 0;
    const condensed = is_condensed();
    const should_hide_menu = !condensed && !has_unpinned_views;
    const should_show_empty_state = !condensed && expanded_views.length === 0;

    const expanded_views_html = render_left_sidebar_expanded_view_items_list({
        expanded_views,
        show_empty_state: should_show_empty_state,
    });
    $("#left-sidebar-navigation-list").html(expanded_views_html);

    const condensed_views_html = primary_condensed_views
        .map((view) => render_left_sidebar_primary_condensed_view_item(view))
        .join("");
    $("#left-sidebar-navigation-list-condensed").html(condensed_views_html);

    $(".left-sidebar-navigation-menu-icon").toggleClass("hide", should_hide_menu);

    if (active_fragment && active_view) {
        $(".top-left-active-filter").removeClass("top-left-active-filter");

        if (active_view) {
            $(`.top_left_${active_view.css_class_suffix}`).addClass("top-left-active-filter");
        }
    }

    const counts = unread.get_counts();
    update_dom_with_unread_counts(counts, true);
    update_drafts_count();
    update_reminders_row();
    const hidden = !user_settings.starred_message_counts;
    update_starred_count(starred_messages.get_count(), hidden);
    update_scheduled_messages_row();
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
