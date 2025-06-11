import $ from "jquery";
import _ from "lodash";

import render_left_sidebar_navigation_condensed_item from "../templates/left_sidebar_navigation_condensed_item.hbs";
import render_left_sidebar_navigation_expanded_item from "../templates/left_sidebar_navigation_expanded_item.hbs";

import * as drafts from "./drafts.ts";
import type {Filter} from "./filter.ts";
import {localstorage} from "./localstorage.ts";
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

let currently_active_unpinned_view: string | null = null;
let all_built_in_views: navigation_views.BuiltInView[] | null = null;

const STATES = {
    EXPANDED: "expanded",
    CONDENSED: "condensed",
};

export function is_condensed(): boolean {
    return ls.get(ls_key) === STATES.CONDENSED;
}

export function is_currently_active_unpinned_view(fragment: string): boolean {
    return currently_active_unpinned_view === fragment;
}

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

export function update_dom_with_unread_counts(
    counts: unread.FullUnreadCountsData,
    skip_animations: boolean,
): void {
    // Note that direct message counts are handled in pm_list.ts.

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

function get_all_built_in_views(): navigation_views.BuiltInView[] {
    all_built_in_views ??= navigation_views.get_built_in_views();
    return all_built_in_views;
}

function refresh_built_in_views_cache(): void {
    all_built_in_views = navigation_views.get_built_in_views();
}

function has_unpinned_views(): boolean {
    return get_all_built_in_views().some((view) => !view.is_pinned);
}

function get_active_view_css_suffix(): string | null {
    const $active_element = $(".top-left-active-filter");
    if ($active_element.length === 0) {
        return null;
    }

    const css_classes = $active_element.attr("class")?.split(" ") ?? [];
    const top_left_class = css_classes.find((cls) => cls.startsWith("top_left_"));

    return top_left_class ? top_left_class.slice(9) : null;
}

export function get_all_views_for_left_sidebar(): navigation_views.BuiltInView[] {
    const pinned_views = get_all_built_in_views().filter((view) => view.is_pinned);
    const unpinned_views = get_all_built_in_views().filter((view) => !view.is_pinned);
    return [...pinned_views, ...unpinned_views];
}

function should_include_scheduled_view(): boolean {
    return scheduled_messages.get_count() > 0;
}

function filter_scheduled_view_if_needed(
    views: navigation_views.BuiltInView[],
): navigation_views.BuiltInView[] {
    const has_scheduled_messages = should_include_scheduled_view();
    const scheduled_view_fragment =
        navigation_views.built_in_views_values.scheduled_messages.fragment;

    if (has_scheduled_messages) {
        return views;
    }

    return views.filter((view) => view.fragment !== scheduled_view_fragment);
}

export function get_views_visible_in_condensed_state(): navigation_views.BuiltInView[] {
    const max_condensed_views = 6;
    const max_condensed_views_with_scheduled = 5;

    let condensed_views = get_all_views_for_left_sidebar().slice(0, max_condensed_views);
    const has_scheduled_messages = should_include_scheduled_view();
    const scheduled_view_fragment =
        navigation_views.built_in_views_values.scheduled_messages.fragment;
    const has_scheduled_view = condensed_views.some(
        (view) => view.fragment === scheduled_view_fragment,
    );

    if (!has_scheduled_messages && has_scheduled_view) {
        condensed_views = filter_scheduled_view_if_needed(condensed_views);
    } else {
        condensed_views = condensed_views.slice(0, max_condensed_views_with_scheduled);
    }

    return condensed_views;
}

function update_currently_active_unpinned_view(active_view_css_suffix: string | null): void {
    if (active_view_css_suffix === null) {
        return;
    }

    const active_view = get_all_built_in_views().find(
        (view) => view.css_class_suffix === active_view_css_suffix,
    );

    if (active_view) {
        currently_active_unpinned_view = active_view.is_pinned ? null : active_view.fragment;
    }
}

function create_views_with_rendering_properties(
    built_in_views: navigation_views.BuiltInView[],
): navigation_views.BuiltInView[] {
    return built_in_views.map((view) => ({
        ...view,
        is_selected: view.home_view_code === user_settings.web_home_view,
        is_temporarily_active: !view.is_pinned && view.fragment === currently_active_unpinned_view,
    }));
}

function get_views_visible_in_expanded_state(
    views_with_properties: navigation_views.BuiltInView[],
): navigation_views.BuiltInView[] {
    return views_with_properties.filter(
        (view) => view.is_pinned || view.fragment === currently_active_unpinned_view,
    );
}

function render_expanded_views_html(views: navigation_views.BuiltInView[]): string {
    return views.map((view) => render_left_sidebar_navigation_expanded_item(view)).join("");
}

function render_condensed_views_html(condensed_views: navigation_views.BuiltInView[]): string {
    return condensed_views
        .map((view) =>
            render_left_sidebar_navigation_condensed_item({
                ...view,
                is_home_view: view.fragment === settings_config.web_home_view_values.inbox.code,
            }),
        )
        .join("");
}

function update_navigation_dom(navigation_html: string, condensed_html: string): void {
    $("#left-sidebar-navigation-list").html(navigation_html);
    $("#left-sidebar-navigation-list-condensed").html(condensed_html);
}

function update_navigation_menu_visibility(): void {
    const should_hide_menu = !is_condensed() && !has_unpinned_views();
    $(".left-sidebar-navigation-menu-icon").toggleClass("hide", should_hide_menu);
}

function update_sidebar_counters(): void {
    update_dom_with_unread_counts(unread.get_counts(), true);
    update_starred_count(starred_messages.get_count(), !user_settings.starred_message_counts);
    update_scheduled_messages_row();
    drafts.set_count(drafts.draft_model.getDraftCount());
}

export function update_navigation_views_visibility(is_to_update_activated_narrow = false): void {
    refresh_built_in_views_cache();
    let active_view_css_suffix: string | null = null;

    // Handle active view detection when not updating activated narrow
    if (!is_to_update_activated_narrow) {
        active_view_css_suffix = get_active_view_css_suffix();
        update_currently_active_unpinned_view(active_view_css_suffix);
    }

    const views_with_properties = create_views_with_rendering_properties(get_all_built_in_views());
    const views_visible_in_expanded_state =
        get_views_visible_in_expanded_state(views_with_properties);
    const views_visible_in_condensed_state = get_views_visible_in_condensed_state();

    const expanded_views_html = render_expanded_views_html(views_visible_in_expanded_state);
    const condensed_views_html = render_condensed_views_html(views_visible_in_condensed_state);

    update_navigation_dom(expanded_views_html, condensed_views_html);

    // Handle active view selection
    if (!is_to_update_activated_narrow && active_view_css_suffix !== null) {
        select_top_left_corner_item(`.top_left_${active_view_css_suffix}`);
    }

    update_navigation_menu_visibility();
    update_sidebar_counters();
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

function handle_unpinned_view_change(selector: string, fragment: string): void {
    if ($(selector).length === 0) {
        currently_active_unpinned_view = fragment;
        update_navigation_views_visibility(true);
    } else if (currently_active_unpinned_view !== null) {
        currently_active_unpinned_view = null;
        update_navigation_views_visibility(true);
    }
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
            handle_unpinned_view_change(
                ".top_left_starred_messages",
                navigation_views.built_in_views_values.starred_messages.fragment,
            );
            select_top_left_corner_item(".top_left_starred_messages");
            return;
        } else if (filter_name === "mentioned") {
            handle_unpinned_view_change(
                ".top_left_mentions",
                navigation_views.built_in_views_values.mentions.fragment,
            );
            select_top_left_corner_item(".top_left_mentions");
            return;
        }
    }
    const term_types = filter.sorted_term_types();
    if (
        _.isEqual(term_types, ["sender", "has-reaction"]) &&
        filter.operands("sender")[0] === people.my_current_email()
    ) {
        handle_unpinned_view_change(
            ".top_left_my_reactions",
            navigation_views.built_in_views_values.my_reactions.fragment,
        );
        select_top_left_corner_item(".top_left_my_reactions");
        return;
    }

    if (currently_active_unpinned_view !== null) {
        currently_active_unpinned_view = null;
        update_navigation_views_visibility(true);
    }

    // If we don't have a specific handler for this narrow, we just clear all.
    select_top_left_corner_item("");
}

function toggle_condensed_navigation_area(): void {
    const $views_label_container = $("#views-label-container");
    const $views_label_icon = $("#toggle-top-left-navigation-area-icon");
    const $left_sidebar_navigation_menu_icon = $(".left-sidebar-navigation-menu-icon");

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
        $left_sidebar_navigation_menu_icon.removeClass("hide");
        save_state(STATES.CONDENSED);
    } else {
        // Toggle into the expanded state
        $views_label_container.addClass("showing-expanded-navigation");
        $views_label_container.removeClass("showing-condensed-navigation");
        $views_label_icon.addClass("rotate-icon-down");
        $views_label_icon.removeClass("rotate-icon-right");
        $left_sidebar_navigation_menu_icon.toggleClass("hide", !has_unpinned_views());
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
    if ($(".top_left_inbox.top_left_row").length === 0) {
        currently_active_unpinned_view = navigation_views.built_in_views_values.inbox.fragment;
        update_navigation_views_visibility(true);
    } else if (currently_active_unpinned_view !== null) {
        currently_active_unpinned_view = null;
        update_navigation_views_visibility(true);
    }
    select_top_left_corner_item(".top_left_inbox");

    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function highlight_recent_view(): void {
    if ($(".top_left_recent_view.top_left_row").length === 0) {
        currently_active_unpinned_view =
            navigation_views.built_in_views_values.recent_view.fragment;
        update_navigation_views_visibility(true);
    } else if (currently_active_unpinned_view !== null) {
        currently_active_unpinned_view = null;
        update_navigation_views_visibility(true);
    }
    select_top_left_corner_item(".top_left_recent_view");

    setTimeout(() => {
        resize.resize_stream_filters_container();
    }, 0);
}

export function highlight_all_messages_view(): void {
    if ($(".top_left_all_messages.top_left_row").length === 0) {
        currently_active_unpinned_view =
            navigation_views.built_in_views_values.all_messages.fragment;
        update_navigation_views_visibility(true);
    } else if (currently_active_unpinned_view !== null) {
        currently_active_unpinned_view = null;
        update_navigation_views_visibility(true);
    }
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

    if ($current_home_view.find(".sidebar-menu-icon").hasClass("hide")) {
        $current_home_view.find(".sidebar-menu-icon").removeClass("hide");
    }

    // Remove class from current home view
    $current_home_view.removeClass("selected-home-view");

    // Add the class to the matching home view
    $new_home_view.addClass("selected-home-view");

    reorder_left_sidebar_navigation_list(new_home_view);
    update_dom_with_unread_counts(res, true);
}

export function initialize(): void {
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
