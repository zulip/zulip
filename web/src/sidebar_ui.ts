import $ from "jquery";

import render_left_sidebar from "../templates/left_sidebar.hbs";
import render_buddy_list_popover from "../templates/popovers/buddy_list_popover.hbs";
import render_right_sidebar from "../templates/right_sidebar.hbs";

import {buddy_list} from "./buddy_list.ts";
import * as channel from "./channel.ts";
import * as compose_ui from "./compose_ui.ts";
import {media_breakpoints_num} from "./css_variables.ts";
import {reorder_left_sidebar_navigation_list} from "./left_sidebar_navigation_area.ts";
import {localstorage} from "./localstorage.ts";
import * as message_lists from "./message_lists.ts";
import * as message_viewport from "./message_viewport.ts";
import {page_params} from "./page_params.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import * as rendered_markdown from "./rendered_markdown.ts";
import * as resize from "./resize.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as spectators from "./spectators.ts";
import {current_user} from "./state_data.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

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
    // Left sidebar toggle icon is attached to middle column.
    $(".app-main .column-left, #navbar-middle").addClass("expanded");
    resize.resize_stream_filters_container();
    left_sidebar_expanded_as_overlay = true;
}

// We use this to display left sidebar without setting
// toggle status
export function show_left_sidebar(): void {
    if (
        // Check if left column is a overlay and is not visible.
        $("#streamlist-toggle").is(":visible") &&
        !left_sidebar_expanded_as_overlay
    ) {
        popovers.hide_all();
        show_streamlist_sidebar();
    } else if (!left_sidebar_expanded_as_overlay) {
        $("body").removeClass("hide-left-sidebar");
    }
}

export function hide_streamlist_sidebar(): void {
    $(".app-main .column-left, #navbar-middle").removeClass("expanded");
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

        if (window.innerWidth >= media_breakpoints_num.xl) {
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
    // make sure home-view and left_sidebar order persists
    reorder_left_sidebar_navigation_list(user_settings.web_home_view);
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
