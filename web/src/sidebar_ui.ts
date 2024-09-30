import $ from "jquery";
import type * as tippy from "tippy.js";

import render_left_sidebar from "../templates/left_sidebar.hbs";
import render_buddy_list_popover from "../templates/popovers/buddy_list_popover.hbs";
import render_right_sidebar from "../templates/right_sidebar.hbs";

import {buddy_list} from "./buddy_list";
import {media_breakpoints_num} from "./css_variables";
import {localstorage} from "./localstorage";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import {page_params} from "./page_params";
import * as popover_menus from "./popover_menus";
import * as rendered_markdown from "./rendered_markdown";
import * as resize from "./resize";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as spectators from "./spectators";
import {current_user} from "./state_data";
import * as ui_util from "./ui_util";
import {user_settings} from "./user_settings";

let buddy_list_popover_instance: tippy.Instance | undefined;

function save_sidebar_toggle_status(): void {
    const ls = localstorage();
    ls.set("left-sidebar", $("body").hasClass("hide-left-sidebar"));
    ls.set("right-sidebar", $("body").hasClass("hide-right-sidebar"));
}

export function restore_sidebar_toggle_status(): void {
    const ls = localstorage();
    if (ls.get("left-sidebar")) {
        $("body").addClass("hide-left-sidebar");
    }
    if (ls.get("right-sidebar")) {
        $("body").addClass("hide-right-sidebar");
    }
}

export let left_sidebar_expanded_as_overlay = false;
export let right_sidebar_expanded_as_overlay = false;

export function hide_userlist_sidebar(): void {
    $(".app-main .column-right").removeClass("expanded");
    right_sidebar_expanded_as_overlay = false;
}

export function show_userlist_sidebar(): void {
    const $userlist_sidebar = $(".app-main .column-right");
    if ($userlist_sidebar.css("display") !== "none") {
        // Return early if the right sidebar is already visible.
        return;
    }

    if (window.innerWidth >= media_breakpoints_num.xl) {
        $("body").removeClass("hide-right-sidebar");
        fix_invite_user_button_flicker();
        return;
    }

    $userlist_sidebar.addClass("expanded");
    fix_invite_user_button_flicker();
    resize.resize_page_components();
    right_sidebar_expanded_as_overlay = true;
}

export function show_streamlist_sidebar(): void {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_stream_filters_container();
    left_sidebar_expanded_as_overlay = true;
}

export function hide_streamlist_sidebar(): void {
    $(".app-main .column-left").removeClass("expanded");
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
        $("#buddy-list-menu-icon").hide();
    } else {
        $("#right-sidebar .invite-user-link").show();
        $("#buddy-list-menu-icon").show();
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

    $("#userlist-toggle-button").on("click", (e) => {
        e.preventDefault();
        e.stopPropagation();

        if (window.innerWidth >= media_breakpoints_num.xl) {
            $("body").toggleClass("hide-right-sidebar");
            if (!$("body").hasClass("hide-right-sidebar")) {
                fix_invite_user_button_flicker();
            }
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

        if (window.innerWidth >= media_breakpoints_num.md) {
            $("body").toggleClass("hide-left-sidebar");
            if (
                message_lists.current !== undefined &&
                window.innerWidth <= media_breakpoints_num.xl
            ) {
                // We expand the middle column width between md and xl breakpoints when the
                // left sidebar is hidden. This can cause the pointer to move out of view.
                message_viewport.scroll_to_selected();
            }
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
                $elt.closest(".left-sidebar-toggle-button").length ||
                $elt.closest("#userlist-toggle-button").length
            ) {
                return;
            }

            // Overrides for certain elements that should not close the sidebars.
            if ($elt.closest(".no-auto-hide-sidebar-overlays").length) {
                return;
            }

            if (
                left_sidebar_expanded_as_overlay &&
                !$elt.closest(".no-auto-hide-left-sidebar-overlay").length
            ) {
                const $left_column = $(".app-main .column-left");
                const click_outside_left_sidebar = !$elt.closest($left_column).length;
                if (click_outside_left_sidebar) {
                    hide_streamlist_sidebar();
                }
            }

            if (
                right_sidebar_expanded_as_overlay &&
                !$elt.closest(".no-auto-hide-right-sidebar-overlay").length
            ) {
                const $right_column = $(".app-main .column-right");
                const click_outside_right_sidebar = !$elt.closest($right_column).length;

                if (click_outside_right_sidebar) {
                    hide_userlist_sidebar();
                }
            }
        },
        {capture: true},
    );
}

export function initialize_left_sidebar(): void {
    const rendered_sidebar = render_left_sidebar({
        is_guest: current_user.is_guest,
        development_environment: page_params.development_environment,
        is_inbox_home_view:
            user_settings.web_home_view === settings_config.web_home_view_values.inbox.code,
        is_all_messages_home_view:
            user_settings.web_home_view === settings_config.web_home_view_values.all_messages.code,
        is_recent_view_home_view:
            user_settings.web_home_view === settings_config.web_home_view_values.recent_topics.code,
        hide_unread_counts: settings_data.should_mask_unread_count(false),
        is_spectator: page_params.is_spectator,
    });

    $("#left-sidebar-container").html(rendered_sidebar);
}

export function initialize_right_sidebar(): void {
    const rendered_sidebar = render_right_sidebar();

    $("#right-sidebar-container").html(rendered_sidebar);

    buddy_list.initialize_tooltips();

    update_invite_user_option();
    if (page_params.is_spectator) {
        rendered_markdown.update_elements(
            $(".right-sidebar .realm-description .rendered_markdown"),
        );
    }

    $("#buddy-list-users-matching-view").on("mouseenter", ".user_sidebar_entry", (e) => {
        const $status_emoji = $(e.target).closest(".user_sidebar_entry").find("img.status-emoji");
        if ($status_emoji.length) {
            const animated_url = $status_emoji.attr("data-animated-url");
            if (animated_url) {
                $status_emoji.attr("src", animated_url);
            }
        }
    });

    $("#buddy-list-users-matching-view").on("mouseleave", ".user_sidebar_entry", (e) => {
        const $status_emoji = $(e.target).closest(".user_sidebar_entry").find("img.status-emoji");
        if ($status_emoji.length) {
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

    $("#user-list").on("click", "#buddy-list-menu-icon", (e) => {
        e.stopPropagation();
        popover_menus.toggle_popover_menu(
            $("#buddy-list-menu-icon")[0]!,
            {
                theme: "popover-menu",
                placement: "right",
                onCreate(instance) {
                    buddy_list_popover_instance = instance;
                    instance.setContent(ui_util.parse_html(render_buddy_list_popover()));
                },
                onHidden() {
                    if (buddy_list_popover_instance !== undefined) {
                        buddy_list_popover_instance.destroy();
                        buddy_list_popover_instance = undefined;
                    }
                },
            },
            {
                show_as_overlay_on_mobile: true,
                show_as_overlay_always: false,
            },
        );
    });
}
