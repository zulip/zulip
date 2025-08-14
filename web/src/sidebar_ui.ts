import $ from "jquery";
import _ from "lodash";

import render_left_sidebar from "../templates/left_sidebar.hbs";
import render_buddy_list_popover from "../templates/popovers/buddy_list_popover.hbs";
import render_right_sidebar from "../templates/right_sidebar.hbs";

import {buddy_list} from "./buddy_list.ts";
import * as channel from "./channel.ts";
import * as compose_ui from "./compose_ui.ts";
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
import * as search_util from "./search_util.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as spectators from "./spectators.ts";
import {current_user} from "./state_data.ts";
import * as stream_list from "./stream_list.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

export let left_sidebar_cursor: ListCursor<JQuery>;

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

export function update_expanded_views_for_search(search_value: string): void {
    if (!search_value) {
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
    for (const view of expanded_views) {
        let show_view = search_util.vanilla_match({
            val: view.name,
            search_terms: search_util.get_search_terms(search_value),
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
        development_environment: page_params.development_environment,
        is_inbox_home_view:
            user_settings.web_home_view === settings_config.web_home_view_values.inbox.code,
        is_all_messages_home_view:
            user_settings.web_home_view === settings_config.web_home_view_values.all_messages.code,
        is_recent_view_home_view:
            user_settings.web_home_view === settings_config.web_home_view_values.recent_topics.code,
        is_spectator: page_params.is_spectator,
        primary_condensed_views,
        expanded_views,
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

function all_rows(): JQuery {
    // NOTE: This function is designed to be used for keyboard navigation purposes.
    // This function returns all the rows in the left sidebar.
    // It is used to find the first key for the ListCursor.
    const $all_rows = $(
        // All left sidebar view rows.
        ".top_left_row, " +
            // All DM and channel rows.
            ".bottom_left_row, " +
            // Views header.
            "#left-sidebar-navigation-area:not(.hidden-by-filters) #views-label-container, " +
            // DM Headers
            "#direct-messages-section-header, " +
            // All channel headers.
            ".stream-list-section-container:not(.no-display) .stream-list-subsection-header",
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
                return $all_rows.first();
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
    const search_value = ui_util.get_left_sidebar_search_term();
    const is_left_sidebar_search_active = search_value !== "";

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
    pm_list.update_private_messages(is_left_sidebar_search_active);

    // Update left sidebar channel list.
    stream_list.update_streams_sidebar();

    resize.resize_page_components();
    left_sidebar_cursor.reset();
    $("#left-sidebar-empty-list-message").toggleClass(
        "hidden",
        !is_left_sidebar_search_active || all_rows().length > 0,
    );
}

const update_left_sidebar_for_search = _.throttle(actually_update_left_sidebar_for_search, 50);

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

export function set_event_handlers(): void {
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
        $search_input.val("");
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
        update_left_sidebar_for_search();
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
}

export function initiate_search(): void {
    popovers.hide_all();

    const $filter = $(".left-sidebar-search-input").expectOne();

    show_left_sidebar();
    $filter.trigger("focus");

    left_sidebar_cursor.reset();
}
