import $ from "jquery";
import {hideAll} from "tippy.js";

import render_playground_links_popover_content from "../templates/playground_links_popover_content.hbs";
import render_user_group_info_popover from "../templates/user_group_info_popover.hbs";
import render_user_group_info_popover_content from "../templates/user_group_info_popover_content.hbs";
import render_user_info_popover_manage_menu from "../templates/user_info_popover_manage_menu.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import * as emoji_picker from "./emoji_picker";
import * as giphy from "./giphy";
import * as message_lists from "./message_lists";
import * as message_viewport from "./message_viewport";
import * as muted_users from "./muted_users";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import * as realm_playground from "./realm_playground";
import * as resize from "./resize";
import * as rows from "./rows";
import * as stream_popover from "./stream_popover";
import * as user_groups from "./user_groups";
import * as user_status_ui from "./user_status_ui";
import * as util from "./util";

let $current_message_info_popover_elem;
let $current_user_info_popover_manage_menu;
let $current_playground_links_popover_elem;

let list_of_popovers = [];

export function clear_for_testing() {
    $current_message_info_popover_elem = undefined;
    $current_user_info_popover_manage_menu = undefined;
    $current_playground_links_popover_elem = undefined;
    list_of_popovers.length = 0;
}

export function elem_to_user_id($elem) {
    return Number.parseInt($elem.attr("data-user-id"), 10);
}

// this utilizes the proxy pattern to intercept all calls to $.fn.popover
// and push the $.fn.data($o, "popover") results to an array.
// this is needed so that when we try to unload popovers, we can kill all dead
// ones that no longer have valid parents in the DOM.
const old_popover = $.fn.popover;
$.fn.popover = Object.assign(function (...args) {
    // apply the jQuery object as `this`, and popover function arguments.
    old_popover.apply(this, args);

    // if there is a valid "popover" key in the jQuery data object then
    // push it to the array.
    if (this.data("popover")) {
        list_of_popovers.push(this.data("popover"));
    }
}, old_popover);

function calculate_info_popover_placement(size, $elt) {
    const ypos = $elt.get_offset_to_window().top;

    if (!(ypos + size / 2 < message_viewport.height() && ypos > size / 2)) {
        if (ypos + size < message_viewport.height()) {
            return "bottom";
        } else if (ypos > size) {
            return "top";
        }
    }

    return undefined;
}

export function hide_user_info_popover_manage_menu() {
    if ($current_user_info_popover_manage_menu !== undefined) {
        $current_user_info_popover_manage_menu.popover("destroy");
        $current_user_info_popover_manage_menu = undefined;
    }
}

export function show_user_info_popover_manage_menu(element, user) {
    const $last_popover_elem = $current_user_info_popover_manage_menu;
    hide_user_info_popover_manage_menu();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        return;
    }

    const is_me = people.is_my_user_id(user.user_id);
    const is_muted = muted_users.is_user_muted(user.user_id);
    const is_system_bot = user.is_system_bot;
    const muting_allowed = !is_me;

    const args = {
        can_mute: muting_allowed && !is_muted,
        can_manage_user: page_params.is_admin && !is_me && !is_system_bot,
        can_unmute: muting_allowed && is_muted,
        is_active: people.is_active_user_for_popover(user.user_id),
        is_bot: user.is_bot,
        user_id: user.user_id,
    };

    const $popover_elt = $(element);
    $popover_elt.popover({
        content: render_user_info_popover_manage_menu(args),
        placement: "bottom",
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $popover_elt.popover("show");
    $current_user_info_popover_manage_menu = $popover_elt;
}

// exporting for testability
export const _test_calculate_info_popover_placement = calculate_info_popover_placement;

function get_user_info_popover_manage_menu_items() {
    if (!$current_user_info_popover_manage_menu) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    const popover_data = $current_user_info_popover_manage_menu.data("popover");
    if (!popover_data) {
        blueslip.error("Cannot find popover data for actions menu.");
        return undefined;
    }

    return $(".user_info_popover_manage_menu li:not(.divider):visible a", popover_data.$tip);
}

function fetch_group_members(member_ids) {
    return member_ids
        .map((m) => people.maybe_get_user_by_id(m))
        .filter((m) => m !== undefined)
        .map((p) => ({
            ...p,
            user_circle_class: buddy_data.get_user_circle_class(p.user_id),
            is_active: people.is_active_user_for_popover(p.user_id),
            user_last_seen_time_status: buddy_data.user_last_seen_time_status(p.user_id),
        }));
}

function sort_group_members(members) {
    return members.sort((a, b) => util.strcmp(a.full_name, b.fullname));
}

// exporting these functions for testing purposes
export const _test_fetch_group_members = fetch_group_members;

export const _test_sort_group_members = sort_group_members;

// element is the target element to pop off of
// user is the user whose profile to show
// message is the message containing it, which should be selected
function show_user_group_info_popover(element, group, message) {
    const $last_popover_elem = $current_message_info_popover_elem;
    // hardcoded pixel height of the popover
    // note that the actual size varies (in group size), but this is about as big as it gets
    const popover_size = 390;
    hide_all();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    message_lists.current.select_id(message.id);
    const $elt = $(element);
    if ($elt.data("popover") === undefined) {
        const args = {
            group_name: group.name,
            group_description: group.description,
            members: sort_group_members(fetch_group_members([...group.members])),
        };
        $elt.popover({
            placement: calculate_info_popover_placement(popover_size, $elt),
            template: render_user_group_info_popover({class: "message-info-popover"}),
            content: render_user_group_info_popover_content(args),
            html: true,
            trigger: "manual",
            fixed: true,
        });
        $elt.popover("show");
        $current_message_info_popover_elem = $elt;
    }
}

function get_action_menu_menu_items() {
    const $current_actions_popover_elem = $("[data-tippy-root] .actions_popover");
    if (!$current_actions_popover_elem) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    return $current_actions_popover_elem.find("li:not(.divider):visible a");
}

export function focus_first_popover_item($items, index = 0) {
    if (!$items) {
        return;
    }

    $items.eq(index).expectOne().trigger("focus");
}

export function popover_items_handle_keyboard(key, $items) {
    if (!$items) {
        return;
    }

    let index = $items.index($items.filter(":focus"));

    if (key === "enter" && index >= 0 && index < $items.length) {
        $items[index].click();
        if ($current_user_info_popover_manage_menu) {
            const $items = get_user_info_popover_manage_menu_items();
            focus_first_popover_item($items);
        }
        return;
    }
    if (index === -1) {
        if ($(".user_info_popover_manage_menu_btn").is(":visible")) {
            index = 1;
        } else {
            index = 0;
        }
    } else if ((key === "down_arrow" || key === "vim_down") && index < $items.length - 1) {
        index += 1;
    } else if ((key === "up_arrow" || key === "vim_up") && index > 0) {
        index -= 1;
    }
    $items.eq(index).trigger("focus");
}

export function focus_first_action_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_action_menu_menu_items();
    focus_first_popover_item($items);
}

export function message_info_popped() {
    return $current_message_info_popover_elem !== undefined;
}

export function hide_message_info_popover() {
    if (message_info_popped()) {
        $current_message_info_popover_elem.popover("destroy");
        $current_message_info_popover_elem = undefined;
    }
}

export function user_info_manage_menu_popped() {
    return $current_user_info_popover_manage_menu !== undefined;
}

export function hide_userlist_sidebar() {
    $(".app-main .column-right").removeClass("expanded");
}

export function hide_pm_list_sidebar() {
    $(".app-main .column-left").removeClass("expanded");
}

export function show_userlist_sidebar() {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
}

function hide_all_user_info_popovers() {
    hide_user_info_popover_manage_menu();
    hide_message_info_popover();
}

export function user_info_popover_manage_menu_handle_keyboard(key) {
    const $items = get_user_info_popover_manage_menu_items();
    popover_items_handle_keyboard(key, $items);
}

// On mobile web, opening the keyboard can trigger a resize event
// (which in turn can trigger a scroll event).  This will have the
// side effect of closing popovers, which we don't want.  So we
// suppress the first hide from scrolling after a resize using this
// variable.
let suppress_scroll_hide = false;

export function set_suppress_scroll_hide() {
    suppress_scroll_hide = true;
}

// Playground_info contains all the data we need to generate a popover of
// playground links for each code block. The element is the target element
// to pop off of.
export function toggle_playground_link_popover(element, playground_info) {
    const $last_popover_elem = $current_playground_links_popover_elem;
    hide_all();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    const $elt = $(element);
    if ($elt.data("popover") === undefined) {
        const ypos = $elt.get_offset_to_window().top;
        $elt.popover({
            // It's unlikely we'll have more than 3-4 playground links
            // for one language, so it should be OK to hardcode 120 here.
            placement: message_viewport.height() - ypos < 120 ? "top" : "bottom",
            title: "",
            content: render_playground_links_popover_content({playground_info}),
            html: true,
            trigger: "manual",
            fixed: true,
        });
        $elt.popover("show");
        $current_playground_links_popover_elem = $elt;
    }
}

export function hide_playground_links_popover() {
    if ($current_playground_links_popover_elem !== undefined) {
        $current_playground_links_popover_elem.popover("destroy");
        $current_playground_links_popover_elem = undefined;
    }
}

export function open_user_status_modal(e) {
    hide_all();

    user_status_ui.open_user_status_modal();

    e.stopPropagation();
    e.preventDefault();
}

export function register_click_handlers() {
    $("#main_div").on("click", ".user-group-mention", function (e) {
        const user_group_id = Number.parseInt($(this).attr("data-user-group-id"), 10);
        const $row = $(this).closest(".message_row");
        e.stopPropagation();
        const message = message_lists.current.get(rows.id($row));
        try {
            const group = user_groups.get_user_group_from_id(user_group_id);
            show_user_group_info_popover(this, group, message);
        } catch {
            // This user group has likely been deleted.
            blueslip.info("Unable to find user group in message" + message.sender_id);
        }
    });

    $("#main_div, #preview_content, #message-history").on(
        "click",
        ".code_external_link",
        function (e) {
            const $view_in_playground_button = $(this);
            const $codehilite_div = $(this).closest(".codehilite");
            e.stopPropagation();
            const playground_info = realm_playground.get_playground_info_for_languages(
                $codehilite_div.data("code-language"),
            );
            // We do the code extraction here and set the target href combining the url_prefix
            // and the extracted code. Depending on whether the language has multiple playground
            // links configured, a popover is show.
            const extracted_code = $codehilite_div.find("code").text();
            if (playground_info.length === 1) {
                const url_prefix = playground_info[0].url_prefix;
                $view_in_playground_button.attr(
                    "href",
                    url_prefix + encodeURIComponent(extracted_code),
                );
            } else {
                for (const $playground of playground_info) {
                    $playground.playground_url =
                        $playground.url_prefix + encodeURIComponent(extracted_code);
                }
                toggle_playground_link_popover(this, playground_info);
            }
        },
    );

    $("body").on("click", ".popover_playground_link", (e) => {
        hide_playground_links_popover();
        e.stopPropagation();
    });

    // Clicking on one's own status emoji should open the user status modal.
    $("#user_presences").on(
        "click",
        ".user_sidebar_entry_me .status-emoji",
        open_user_status_modal,
    );

    {
        let last_scroll = 0;

        $(document).on("scroll", () => {
            if (suppress_scroll_hide) {
                suppress_scroll_hide = false;
                return;
            }

            const date = Date.now();

            // only run `popovers.hide_all()` if the last scroll was more
            // than 250ms ago.
            if (date - last_scroll > 250) {
                hide_all();
            }

            // update the scroll time on every event to make sure it doesn't
            // retrigger `hide_all` while still scrolling.
            last_scroll = date;
        });
    }
}

export function any_active() {
    // True if any popover (that this module manages) is currently shown.
    // Expanded sidebars on mobile view count as popovers as well.
    return (
        popover_menus.any_active() ||
        stream_popover.stream_popped() ||
        emoji_picker.reactions_popped() ||
        $("[class^='column-'].expanded").length
    );
}

// This function will hide all true popovers (the streamlist and
// userlist sidebars use the popover infrastructure, but doesn't work
// like a popover structurally).
export function hide_all_except_sidebars(opts) {
    $(".has_popover").removeClass("has_popover has_actions_popover has_emoji_popover");
    if (!opts || !opts.not_hide_tippy_instances) {
        // hideAll hides all tippy instances (tooltips and popovers).
        hideAll();
    }
    emoji_picker.hide_emoji_popover();
    giphy.hide_giphy_popover();
    stream_popover.hide_stream_popover();
    hide_all_user_info_popovers();
    hide_playground_links_popover();

    // look through all the popovers that have been added and removed.
    for (const $o of list_of_popovers) {
        if (!document.body.contains($o.$element[0]) && $o.$tip) {
            $o.$tip.remove();
        }
    }
    list_of_popovers = [];
}

// This function will hide all the popovers, including the mobile web
// or narrow window sidebars.
export function hide_all(not_hide_tippy_instances) {
    hide_userlist_sidebar();
    stream_popover.hide_streamlist_sidebar();
    hide_all_except_sidebars({
        not_hide_tippy_instances,
    });
}

export function compute_placement(
    $elt,
    popover_height,
    popover_width,
    prefer_vertical_positioning,
) {
    const client_rect = $elt.get(0).getBoundingClientRect();
    const distance_from_top = client_rect.top;
    const distance_from_bottom = message_viewport.height() - client_rect.bottom;
    const distance_from_left = client_rect.left;
    const distance_from_right = message_viewport.width() - client_rect.right;

    const elt_will_fit_horizontally =
        distance_from_left + $elt.width() / 2 > popover_width / 2 &&
        distance_from_right + $elt.width() / 2 > popover_width / 2;

    const elt_will_fit_vertically =
        distance_from_bottom + $elt.height() / 2 > popover_height / 2 &&
        distance_from_top + $elt.height() / 2 > popover_height / 2;

    // default to placing the popover in the center of the screen
    let placement = "viewport_center";

    // prioritize left/right over top/bottom
    if (distance_from_top > popover_height && elt_will_fit_horizontally) {
        placement = "top";
    }
    if (distance_from_bottom > popover_height && elt_will_fit_horizontally) {
        placement = "bottom";
    }

    if (prefer_vertical_positioning && placement !== "viewport_center") {
        // If vertical positioning is preferred and the popover fits in
        // either top or bottom position then return.
        return placement;
    }

    if (distance_from_left > popover_width && elt_will_fit_vertically) {
        placement = "left";
    }
    if (distance_from_right > popover_width && elt_will_fit_vertically) {
        placement = "right";
    }

    return placement;
}

export function initialize() {
    overlays.register_pre_open_hook(hide_all);
    overlays.register_pre_close_hook(hide_all);
}
