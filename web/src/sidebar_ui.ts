import $ from "jquery";
import _ from "lodash";

import render_left_sidebar from "../templates/left_sidebar.hbs";
import render_buddy_list_popover from "../templates/popovers/buddy_list_popover.hbs";
import render_right_sidebar from "../templates/right_sidebar.hbs";

import type {TypeaheadInputElement} from "./bootstrap_typeahead.ts";
import {Typeahead} from "./bootstrap_typeahead.ts";
import {buddy_list} from "./buddy_list.ts";
import * as channel from "./channel.ts";
import * as compose_ui from "./compose_ui.ts";
import {$t} from "./i18n.ts";
import * as keydown_util from "./keydown_util.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import {ListCursor} from "./list_cursor.ts";
import {localstorage} from "./localstorage.ts";
import * as message_lists from "./message_lists.ts";
import * as message_reminder from "./message_reminder.ts";
import * as message_viewport from "./message_viewport.ts";
import {page_params} from "./page_params.ts";
import * as pm_list from "./pm_list.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import * as resize from "./resize.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as scroll_util from "./scroll_util.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as spectators from "./spectators.ts";
import {current_user} from "./state_data.ts";
import * as stream_list from "./stream_list.ts";
import * as topic_filter_pill from "./topic_filter_pill.ts";
import type {TopicFilterPill, TopicFilterPillWidget} from "./topic_filter_pill.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

const LEFT_SIDEBAR_NAVIGATION_AREA_TITLE = $t({defaultMessage: "VIEWS"});

export let left_sidebar_cursor: ListCursor<JQuery>;

// Pill widget for topic-state filtering (e.g., is:followed)
// in the left sidebar search bar. This enables users to filter
// the topic list across all channels by followed state, using
// the same pill infrastructure as the zoomed topic filter.
let left_sidebar_pill_widget: TopicFilterPillWidget | null = null;

// The full placeholder text shown when no filter pill is active.
const LEFT_SIDEBAR_FILTER_PLACEHOLDER = $t({defaultMessage: "Filter left sidebar"});
// Shortened placeholder shown when a filter pill is active,
// so the pill + placeholder fit on a single line.
const LEFT_SIDEBAR_FILTER_PLACEHOLDER_SHORT = $t({defaultMessage: "Filter"});

/**
 * Sync the current pill state to ui_util so that topic_list.ts
 * can read it without importing sidebar_ui (which would create
 * a dependency cycle). Must be called whenever pills are added
 * or removed from the left sidebar filter.
 */
function sync_left_sidebar_pill_state(): void {
    if (left_sidebar_pill_widget === null) {
        ui_util.set_left_sidebar_filter_pill_syntax("");
        return;
    }

    const pills = left_sidebar_pill_widget.items();
    if (pills.length === 0) {
        ui_util.set_left_sidebar_filter_pill_syntax("");
        return;
    }

    // Currently we support a single topic-state filter pill at a time.
    ui_util.set_left_sidebar_filter_pill_syntax(pills[0]!.syntax);
}

function clear_left_sidebar_pills(): void {
    if (left_sidebar_pill_widget !== null) {
        left_sidebar_pill_widget.clear(true);
    }
    update_left_sidebar_filter_placeholder();
}

/**
 * Update the placeholder text in the left sidebar search input.
 * When a filter pill is active, we shorten the placeholder to
 * just "Filter" so the pill and placeholder fit on one line.
 */
function update_left_sidebar_filter_placeholder(): void {
    const $input = $("#left-sidebar-filter-query");
    if ($input.length === 0) {
        return;
    }
    const has_pills =
        left_sidebar_pill_widget !== null && left_sidebar_pill_widget.items().length > 0;
    $input.attr(
        "data-placeholder",
        has_pills ? LEFT_SIDEBAR_FILTER_PLACEHOLDER_SHORT : LEFT_SIDEBAR_FILTER_PLACEHOLDER,
    );
}

function save_sidebar_toggle_status(): void {
    const ls = localstorage();
    ls.set("left-sidebar", $("body").hasClass("hide-left-sidebar"));

    if (!page_params.is_spectator) {
        // The right sidebar is never shown in the spectator mode;
        // avoid interacting with local storage state for it.
        ls.set("right-sidebar", $("body").hasClass("hide-right-sidebar"));
    }
}

export function restore_sidebar_toggle_status(): void {
    const ls = localstorage();
    if (ls.get("left-sidebar")) {
        $("body").addClass("hide-left-sidebar");
    }

    if (!page_params.is_spectator && ls.get("right-sidebar")) {
        // The right sidebar is never shown in the spectator mode;
        // avoid processing local storage state for hiding the right
        // sidebar.
        $("body").addClass("hide-right-sidebar");
    }
}

export let left_sidebar_expanded_as_overlay = false;
export let right_sidebar_expanded_as_overlay = false;

export function hide_userlist_sidebar(): void {
    const $userlist_sidebar = $(".app-main .column-right");
    $userlist_sidebar.removeClass("expanded topmost-overlay");
    right_sidebar_expanded_as_overlay = false;
}

export function show_userlist_sidebar(): void {
    const $streamlist_sidebar = $(".app-main .column-left");
    const $userlist_sidebar = $(".app-main .column-right");
    if ($userlist_sidebar.css("display") !== "none") {
        // Return early if the right sidebar is already visible.
        return;
    }

    if (ui_util.matches_viewport_state("gte_xl_min")) {
        $("body").removeClass("hide-right-sidebar");
        fix_invite_user_button_flicker();
        return;
    }

    $userlist_sidebar.addClass("expanded");
    if (left_sidebar_expanded_as_overlay) {
        $userlist_sidebar.addClass("topmost-overlay");
        $streamlist_sidebar.removeClass("topmost-overlay");
    }
    fix_invite_user_button_flicker();
    resize.resize_page_components();
    right_sidebar_expanded_as_overlay = true;
}

export function show_streamlist_sidebar(): void {
    const $userlist_sidebar = $(".app-main .column-right");
    const $streamlist_sidebar = $(".app-main .column-left");
    // Left sidebar toggle icon is attached to middle column.
    $(".app-main .column-left, #navbar-middle").addClass("expanded");
    if (right_sidebar_expanded_as_overlay) {
        $streamlist_sidebar.addClass("topmost-overlay");
        $userlist_sidebar.removeClass("topmost-overlay");
    }
    resize.resize_stream_filters_container();
    left_sidebar_expanded_as_overlay = true;
}

// We use this to display left sidebar without setting
// toggle status
export function show_left_sidebar(): void {
    if (
        // Check if left column is a overlay and is not visible.
        $("#streamlist-toggle").css("display") !== "none" &&
        !left_sidebar_expanded_as_overlay
    ) {
        popovers.hide_all();
        show_streamlist_sidebar();
    } else if (!left_sidebar_expanded_as_overlay) {
        $("body").removeClass("hide-left-sidebar");
    }
}

export function hide_streamlist_sidebar(): void {
    const $streamlist_sidebar = $(".app-main .column-left");
    $(".app-main .column-left, #navbar-middle").removeClass("expanded");
    $streamlist_sidebar.removeClass("topmost-overlay");
    left_sidebar_expanded_as_overlay = false;
}

export function any_sidebar_expanded_as_overlay(): boolean {
    return left_sidebar_expanded_as_overlay || right_sidebar_expanded_as_overlay;
}

export function update_invite_user_option(): void {
    if (
        !settings_data.user_can_invite_users_by_email() &&
        !settings_data.user_can_create_multiuse_invite()
    ) {
        $("#right-sidebar .invite-user-link").hide();
    } else {
        $("#right-sidebar .invite-user-link").show();
    }
}

export function hide_all(): void {
    hide_streamlist_sidebar();
    hide_userlist_sidebar();
}

function fix_invite_user_button_flicker(): void {
    // Keep right sidebar hidden after browser renders it to avoid
    // flickering of "Invite more users" button. Since the user list
    // is a complex component browser takes time for it to render
    // causing the invite button to render first.
    $("body").addClass("hide-right-sidebar-by-visibility");
    // Show the right sidebar after the browser has completed the above render.
    setTimeout(() => {
        $("body").removeClass("hide-right-sidebar-by-visibility");
    }, 0);
}

export function initialize(): void {
    $("body").on("click", ".login_button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = spectators.build_login_link();
    });

    $("body").on("keydown", ".login_button", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            window.location.href = spectators.build_login_link();
        }
    });

    $("#userlist-toggle-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        if (ui_util.matches_viewport_state("gte_xl_min")) {
            $("body").toggleClass("hide-right-sidebar");
            if (!$("body").hasClass("hide-right-sidebar")) {
                fix_invite_user_button_flicker();
            }
            // We recheck the scrolling-button status of the compose
            // box, which may change for users who've chosen to
            // use full width on wide screens.
            compose_ui.maybe_show_scrolling_formatting_buttons(
                "#message-formatting-controls-container",
            );
            save_sidebar_toggle_status();
            return;
        }

        if (right_sidebar_expanded_as_overlay) {
            hide_userlist_sidebar();
            return;
        }
        show_userlist_sidebar();
    });

    $(".left-sidebar-toggle-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        if (ui_util.matches_viewport_state("gte_md_min")) {
            $("body").toggleClass("hide-left-sidebar");
            if (
                message_lists.current !== undefined &&
                !ui_util.matches_viewport_state("gte_xl_min")
            ) {
                // We expand the middle column width between md and xl breakpoints when the
                // left sidebar is hidden. This can cause the pointer to move out of view.
                message_viewport.scroll_to_selected();
            }
            // We recheck the scrolling-button status of the compose
            // box, which may change for users who've chosen to
            // use full width on wide screens.
            compose_ui.maybe_show_scrolling_formatting_buttons(
                "#message-formatting-controls-container",
            );
            save_sidebar_toggle_status();
            return;
        }

        if (left_sidebar_expanded_as_overlay) {
            hide_streamlist_sidebar();
            return;
        }
        show_streamlist_sidebar();
    });

    // Hide left / right sidebar on click outside.
    document.addEventListener(
        "click",
        (e) => {
            if (!(left_sidebar_expanded_as_overlay || right_sidebar_expanded_as_overlay)) {
                return;
            }

            if (!(e.target instanceof Element)) {
                return;
            }

            const $elt = $(e.target);
            // Since sidebar toggle buttons have their own click handlers, don't handle them here.
            if (
                $elt.closest(".left-sidebar-toggle-button").length > 0 ||
                $elt.closest("#userlist-toggle-button").length > 0
            ) {
                return;
            }

            // Overrides for certain elements that should not close the sidebars.
            if ($elt.closest(".no-auto-hide-sidebar-overlays").length > 0) {
                return;
            }

            if (
                left_sidebar_expanded_as_overlay &&
                $elt.closest(".auto-hide-left-sidebar-overlay").length > 0
            ) {
                hide_streamlist_sidebar();
            }

            if (
                left_sidebar_expanded_as_overlay &&
                $elt.closest(".no-auto-hide-left-sidebar-overlay").length === 0
            ) {
                const $left_column = $(".app-main .column-left");
                const click_outside_left_sidebar = $elt.closest($left_column).length === 0;
                if (click_outside_left_sidebar) {
                    hide_streamlist_sidebar();
                }
            }

            if (
                right_sidebar_expanded_as_overlay &&
                $elt.closest(".no-auto-hide-right-sidebar-overlay").length === 0
            ) {
                const $right_column = $(".app-main .column-right");
                const click_outside_right_sidebar = $elt.closest($right_column).length === 0;

                if (click_outside_right_sidebar) {
                    hide_userlist_sidebar();
                }
            }
        },
        {capture: true},
    );
}

export function update_expanded_views_for_search(search_term: string): void {
    if (!search_term) {
        // Show all the views if there is no search term.
        $("#left-sidebar-navigation-area, #left-sidebar-navigation-list .top_left_row").removeClass(
            "hidden-by-filters",
        );
        left_sidebar_navigation_area.update_scheduled_messages_row();
        left_sidebar_navigation_area.update_reminders_row();
        return;
    }

    let any_view_visible = false;
    const expanded_views = left_sidebar_navigation_area.get_built_in_views();
    const show_all_views = util.prefix_match({
        value: LEFT_SIDEBAR_NAVIGATION_AREA_TITLE,
        search_term,
    });
    for (const view of expanded_views) {
        let show_view =
            show_all_views ||
            util.prefix_match({
                value: view.name,
                search_term,
            });
        const $view = $(`.top_left_${view.css_class_suffix}`);

        if (show_view && $view.hasClass("top_left_scheduled_messages")) {
            show_view = scheduled_messages.get_count() !== 0;
        }

        if (show_view && $view.hasClass("top_left_reminders")) {
            show_view = message_reminder.get_count() !== 0;
        }
        $view.toggleClass("hidden-by-filters", !show_view);
        any_view_visible ||= show_view;
    }
    // Hide "VIEWS" header if all views are hidden.
    $("#left-sidebar-navigation-area").toggleClass("hidden-by-filters", !any_view_visible);
}

export function initialize_left_sidebar(): void {
    const primary_condensed_views =
        left_sidebar_navigation_area.get_built_in_primary_condensed_views();
    const expanded_views = left_sidebar_navigation_area.get_built_in_views();

    const rendered_sidebar = render_left_sidebar({
        is_guest: current_user.is_guest,
        is_spectator: page_params.is_spectator,
        primary_condensed_views,
        expanded_views,
        LEFT_SIDEBAR_NAVIGATION_AREA_TITLE,
        LEFT_SIDEBAR_DIRECT_MESSAGES_TITLE: pm_list.LEFT_SIDEBAR_DIRECT_MESSAGES_TITLE,
    });

    $("#left-sidebar-container").html(rendered_sidebar);
    // make sure home-view and left_sidebar order persists
    left_sidebar_navigation_area.reorder_left_sidebar_navigation_list(user_settings.web_home_view);
    stream_list.update_unread_counts_visibility();
    initialize_left_sidebar_cursor();
    set_event_handlers();
}

export function focus_topic_search_filter(): void {
    popovers.hide_all();
    show_left_sidebar();
    const $filter = $("#topic_filter_query");
    $filter.trigger("focus");
}

export function initialize_right_sidebar(): void {
    const rendered_sidebar = render_right_sidebar();

    $("#right-sidebar-container").html(rendered_sidebar);

    buddy_list.initialize_tooltips();

    update_invite_user_option();

    $("#buddy-list-users-matching-view").on("mouseenter", ".user_sidebar_entry", (e) => {
        const $status_emoji = $(e.target).closest(".user_sidebar_entry").find("img.status-emoji");
        if ($status_emoji.length > 0) {
            const animated_url = $status_emoji.attr("data-animated-url");
            if (animated_url) {
                $status_emoji.attr("src", animated_url);
            }
        }
    });

    $("#buddy-list-users-matching-view").on("mouseleave", ".user_sidebar_entry", (e) => {
        const $status_emoji = $(e.target).closest(".user_sidebar_entry").find("img.status-emoji");
        if ($status_emoji.length > 0) {
            const still_url = $status_emoji.attr("data-still-url");
            if (still_url) {
                $status_emoji.attr("src", still_url);
            }
        }
    });

    $("#buddy-list-users-matching-view-container").on(
        "click",
        ".buddy-list-subsection-header",
        (e) => {
            e.stopPropagation();
            buddy_list.toggle_users_matching_view_section();
        },
    );

    $("#buddy-list-participants-container").on("click", ".buddy-list-subsection-header", (e) => {
        e.stopPropagation();
        buddy_list.toggle_participants_section();
    });

    $("#buddy-list-other-users-container").on("click", ".buddy-list-subsection-header", (e) => {
        e.stopPropagation();
        buddy_list.toggle_other_users_section();
    });

    function close_buddy_list_popover(): void {
        if (popover_menus.popover_instances.buddy_list !== null) {
            popover_menus.popover_instances.buddy_list.destroy();
            popover_menus.popover_instances.buddy_list = null;
        }
    }

    popover_menus.register_popover_menu("#buddy-list-menu-icon", {
        theme: "popover-menu",
        placement: "right",
        onCreate(instance) {
            popover_menus.popover_instances.buddy_list = instance;
            instance.setContent(
                ui_util.parse_html(
                    render_buddy_list_popover({
                        display_style_options: settings_config.user_list_style_values,
                        can_invite_users:
                            settings_data.user_can_invite_users_by_email() ||
                            settings_data.user_can_create_multiuse_invite(),
                    }),
                ),
            );
        },
        onMount() {
            const current_user_list_style =
                settings_preferences.user_settings_panel.settings_object.user_list_style;
            $("#buddy-list-actions-menu-popover")
                .find(`.user_list_style_choice[value=${current_user_list_style}]`)
                .prop("checked", true);
        },
        onHidden() {
            close_buddy_list_popover();
        },
    });

    $("body").on(
        "click",
        "#buddy-list-actions-menu-popover .display-style-selector",
        function (this: HTMLElement) {
            const data = {user_list_style: $(this).val()};
            const current_user_list_style =
                settings_preferences.user_settings_panel.settings_object.user_list_style;

            if (current_user_list_style === data.user_list_style) {
                close_buddy_list_popover();
                return;
            }

            void channel.patch({
                url: "/json/settings",
                data,
                success() {
                    close_buddy_list_popover();
                },
            });
        },
    );
}

function get_header_rows_selectors(): string {
    return (
        // Views header.
        "#left-sidebar-navigation-area:not(.hidden-by-filters) #views-label-container, " +
        // DM Headers
        "#left_sidebar_scroll_container:not(.direct-messages-hidden-by-filters) #direct-messages-section-header, " +
        // All channel headers.
        ".stream-list-section-container:not(.no-display) .stream-list-subsection-header"
    );
}

function all_rows(): JQuery {
    // NOTE: This function is designed to be used for keyboard navigation purposes.
    // This function returns all the rows in the left sidebar.
    // It is used to find the first key for the ListCursor.
    const $all_rows = $(
        // All left sidebar view rows.
        ".top_left_row, " +
            // All DM and channel rows.
            ".bottom_left_row, " +
            get_header_rows_selectors(),
    ).not(".hidden-by-filters");
    // Remove rows hidden due to being inactive or muted.
    const $inactive_or_muted_rows = $(
        "#streams_list:not(.is_searching) .stream-list-section-container:not(.showing-inactive-or-muted)" +
            " .inactive-or-muted-in-channel-folder .bottom_left_row:not(.hidden-by-filters)",
    );
    // Remove rows in collapsed sections / folders.
    const $collapsed_views = $(
        "#views-label-container.showing-condensed-navigation +" +
            " #left-sidebar-navigation-list .top_left_row",
    ).not(".top-left-active-filter");
    const $collapsed_channels = $(
        ".stream-list-section-container.collapsed .narrow-filter:not(.stream-expanded) .bottom_left_row",
    );
    const $hidden_topic_rows = $(
        ".stream-list-section-container.collapsed .topic-list-item:not(.active-sub-filter).bottom_left_row",
    );

    // Exclude toggle inactive / muted channels row from the list of rows if user is searching.
    const $toggle_inactive_or_muted_channels_row = $(
        "#streams_list.is_searching .stream-list-toggle-inactive-or-muted-channels.bottom_left_row",
    );

    return $all_rows
        .not($inactive_or_muted_rows)
        .not($collapsed_views)
        .not($collapsed_channels)
        .not($hidden_topic_rows)
        .not($toggle_inactive_or_muted_channels_row);
}

class LeftSidebarListCursor extends ListCursor<JQuery> {
    override adjust_scroll($li: JQuery): void {
        $li[0]!.scrollIntoView({
            block: "center",
        });
    }
}

export function initialize_left_sidebar_cursor(): void {
    left_sidebar_cursor = new LeftSidebarListCursor({
        list: {
            // `scroll_container_selector` is not used
            // since we override `adjust_scroll` above.
            scroll_container_selector: "#left-sidebar",
            find_li(opts) {
                return opts.key;
            },
            first_key(): JQuery | undefined {
                const $all_rows = all_rows();
                if ($all_rows.length === 0) {
                    return undefined;
                }
                const $non_header_rows = $all_rows.not($(get_header_rows_selectors()));
                return $non_header_rows.first();
            },
            next_key($key) {
                const $all_rows = all_rows();
                if ($all_rows.length === 0) {
                    return undefined;
                }

                const key_index = $all_rows.index($key);
                if (key_index === -1 || key_index === $all_rows.length - 1) {
                    return $key;
                }
                const $next = $all_rows.eq(key_index + 1);
                return $next;
            },
            prev_key($key) {
                const $all_rows = all_rows();
                if ($all_rows.length === 0) {
                    return undefined;
                }

                const key_index = $all_rows.index($key);
                if (key_index <= 0) {
                    return $key;
                }
                const $prev = $all_rows.eq(key_index - 1);
                return $prev;
            },
        },
        highlight_class: "highlighted_row",
    });
}

function actually_update_left_sidebar_for_search(): void {
    // Sync pill state to ui_util so topic_list.ts can read it
    // without importing sidebar_ui (avoiding a dependency cycle).
    sync_left_sidebar_pill_state();
    const search_value = ui_util.get_left_sidebar_search_term();
    const has_filter_pill = ui_util.get_left_sidebar_filter_pill_syntax() !== "";
    // Consider the search active if either text is typed or a
    // topic-state filter pill (e.g., is:followed) is active.
    const is_left_sidebar_search_active = search_value !== "" || has_filter_pill;
    left_sidebar_cursor.set_is_highlight_visible(is_left_sidebar_search_active);

    // Update left sidebar navigation area.
    update_expanded_views_for_search(search_value);
    const $views_label_container = $("#views-label-container");
    const $views_label_icon = $("#toggle-top-left-navigation-area-icon");
    if (
        !$views_label_container.hasClass("showing-expanded-navigation") &&
        is_left_sidebar_search_active
    ) {
        left_sidebar_navigation_area.expand_views($views_label_container, $views_label_icon);
    } else if (!is_left_sidebar_search_active) {
        left_sidebar_navigation_area.restore_views_state();
    }

    // Update left sidebar DM list.
    pm_list.update_private_messages();

    // Update left sidebar channel list.
    stream_list.update_streams_sidebar();

    resize.resize_page_components();
    left_sidebar_cursor.reset();
    $("#left-sidebar-empty-list-message").toggleClass(
        "hidden",
        !is_left_sidebar_search_active || all_rows().length > 0,
    );
}

// Scroll position before user started searching.
let pre_search_scroll_position = 0;
let previous_search_term = "";

const update_left_sidebar_for_search = _.throttle(() => {
    const search_term = ui_util.get_left_sidebar_search_term();
    const is_previous_search_term_empty = previous_search_term === "";
    previous_search_term = search_term;

    const left_sidebar_scroll_container = scroll_util.get_left_sidebar_scroll_container();
    if (search_term === "") {
        requestAnimationFrame(() => {
            actually_update_left_sidebar_for_search();
            // Restore previous scroll position.
            left_sidebar_scroll_container.scrollTop(pre_search_scroll_position);
        });
    } else {
        if (is_previous_search_term_empty) {
            // Store original scroll position to be restored later.
            pre_search_scroll_position = left_sidebar_scroll_container.scrollTop()!;
        }
        requestAnimationFrame(() => {
            actually_update_left_sidebar_for_search();
            // Always scroll to top when there is a search term present.
            left_sidebar_scroll_container.scrollTop(0);
        });
    }
}, 50);

function focus_left_sidebar_filter(e: JQuery.ClickEvent): void {
    left_sidebar_cursor.reset();
    e.stopPropagation();
}

export function focus_pm_search_filter(): void {
    popovers.hide_all();
    show_left_sidebar();
    const $filter = $(".direct-messages-list-filter").expectOne();
    $filter.trigger("focus");
}

/**
 * Set up the typeahead and pill widget for the left sidebar
 * search input, enabling topic-state filters like is:followed.
 *
 * This reuses the same topic_filter_pill infrastructure from the
 * zoomed-in "all topics" filter (topic_list.ts), but scoped to
 * the top-level left sidebar search bar. Only followed/unfollowed
 * options are shown per issue #36878; resolved/unresolved filters
 * are tracked separately in issue #36877.
 */
function setup_left_sidebar_typeahead(): void {
    const $input = $("#left-sidebar-filter-query");
    const $pill_container = $("#left-sidebar-filter-input");

    if ($input.length === 0 || $pill_container.length === 0) {
        return;
    }

    left_sidebar_pill_widget = topic_filter_pill.create_pills($pill_container);

    const typeahead_input: TypeaheadInputElement = {
        $element: $input,
        type: "contenteditable",
    };

    const options = {
        source() {
            const pills = left_sidebar_pill_widget!.items();
            const current_syntaxes = new Set(pills.map((pill) => pill.syntax));
            const query = $input.text().trim();
            // Only show followed/unfollowed options; resolved/unresolved
            // are excluded per issue #36878 scope (see #36877 for those).
            return topic_filter_pill.filter_options.filter((option) => {
                if (option.syntax.endsWith("resolved")) {
                    return false;
                }
                // Don't show pills that are already active.
                if (current_syntaxes.has(option.syntax)) {
                    return false;
                }
                // Some pills (e.g., -is:followed) require a specific
                // prefix before they appear in the typeahead, to avoid
                // cluttering the suggestions for common use cases.
                if (
                    option.match_prefix_required &&
                    !query.startsWith(option.match_prefix_required)
                ) {
                    return false;
                }
                return true;
            });
        },
        item_html(item: TopicFilterPill) {
            return typeahead_helper.render_topic_state(item.label);
        },
        matcher(item: TopicFilterPill, query: string) {
            // Only show the typeahead dropdown when the query contains
            // a colon, matching the pattern "is:" or "-is:".
            return (
                query.includes(":") &&
                (item.syntax.toLowerCase().startsWith(query.toLowerCase()) ||
                    (item.syntax.startsWith("-") &&
                        item.syntax.slice(1).toLowerCase().startsWith(query.toLowerCase())))
            );
        },
        sorter(items: TopicFilterPill[]) {
            return items;
        },
        updater(item: TopicFilterPill) {
            // Replace any existing pill with the newly selected one,
            // since we only support one topic-state filter at a time.
            left_sidebar_pill_widget!.clear(true);
            left_sidebar_pill_widget!.appendValue(item.syntax);
            $input.text("");
            $input.trigger("focus");
            // Update placeholder to the shorter text so pill + placeholder
            // fit on one line.
            update_left_sidebar_filter_placeholder();
            // Re-render the sidebar to apply the topic-state filter.
            actually_update_left_sidebar_for_search();
            return "";
        },
        stopAdvance: true,
        // Use dropup to match compose typeahead direction.
        dropup: true,
    };

    new Typeahead(typeahead_input, options);

    // Prevent Enter from submitting while typing filter text,
    // and let comma pass through for potential future use.
    $input.on("keydown", (e: JQuery.KeyDownEvent) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
        } else if (e.key === ",") {
            e.stopPropagation();
            return;
        }
    });

    // When a pill is removed (e.g., via backspace or clicking X),
    // re-render the sidebar and restore the full placeholder text.
    left_sidebar_pill_widget.onPillRemove(() => {
        update_left_sidebar_filter_placeholder();
        actually_update_left_sidebar_for_search();
    });
}

export function set_event_handlers(): void {
    // The left sidebar search input is now a contenteditable div
    // inside a pill container. We attach events to the contenteditable
    // element for keyboard handling, and to the pill container for
    // input events (which fire on the container for contenteditable).
    const $search_input = $(".left-sidebar-search-input").expectOne();

    function keydown_enter_key(): void {
        const $row = left_sidebar_cursor.get_key();

        if ($row === undefined) {
            // This can happen for empty searches, no need to warn.
            return;
        }

        if ($row[0]!.id === "views-label-container") {
            $row.find("#toggle-top-left-navigation-area-icon").trigger("click");
            return;
        }

        if (
            $row.hasClass("stream-list-toggle-inactive-or-muted-channels") ||
            $row[0]!.id === "direct-messages-section-header" ||
            $row.hasClass("stream-list-subsection-header")
        ) {
            $row.trigger("click");
            return;
        }
        // Clear search input so that there is no confusion
        // about which search input is active.
        $search_input.text("");
        const $nearest_link = $row.find("a").first();
        if ($nearest_link.length > 0) {
            // If the row has a link, we click it.
            $nearest_link[0]!.click();
        } else {
            // If the row does not have a link,
            // let the browser handle it or add special
            // handling logic for it here.
        }
        // Don't trigger `input` which confuses the search input
        // for zoomed in topic search.
        actually_update_left_sidebar_for_search();
        $search_input.trigger("blur");
    }

    keydown_util.handle({
        $elem: $search_input,
        handlers: {
            Enter() {
                keydown_enter_key();
                return true;
            },
            ArrowUp() {
                left_sidebar_cursor.prev();
                return true;
            },
            ArrowDown() {
                left_sidebar_cursor.next();
                return true;
            },
        },
    });

    $search_input.on("click", focus_left_sidebar_filter);
    $search_input.on("focusout", () => {
        left_sidebar_cursor.clear();
    });
    $search_input.on("input", update_left_sidebar_for_search);

    // Set up the typeahead and pill widget for topic-state
    // filtering (e.g., is:followed) in the left sidebar.
    setup_left_sidebar_typeahead();

    // When the close button is clicked, clear pills too.
    $("#left-sidebar-search .input-close-filter-button").on("click", () => {
        clear_left_sidebar_pills();
        $search_input.text("");
        actually_update_left_sidebar_for_search();
    });
}

export function initiate_search(): void {
    popovers.hide_all();

    const $filter = $(".left-sidebar-search-input").expectOne();

    show_left_sidebar();
    $filter.trigger("focus");

    left_sidebar_cursor.reset();
}
