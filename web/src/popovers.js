import $ from "jquery";
import {hideAll} from "tippy.js";
import url_template_lib from "url-template";

import render_playground_links_popover_content from "../templates/playground_links_popover_content.hbs";

import * as blueslip from "./blueslip";
import * as emoji_picker from "./emoji_picker";
import * as message_viewport from "./message_viewport";
import * as overlays from "./overlays";
import * as popover_menus from "./popover_menus";
import * as realm_playground from "./realm_playground";
import * as resize from "./resize";
import * as stream_popover from "./stream_popover";
import * as user_card_popover from "./user_card_popover";
import * as user_group_popover from "./user_group_popover";

let $current_playground_links_popover_elem;
let list_of_popovers = [];

export function clear_for_testing() {
    $current_playground_links_popover_elem = undefined;
    list_of_popovers.length = 0;
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
        if (user_card_popover.user_info_manage_menu_popped()) {
            const $items = user_card_popover.get_user_info_popover_manage_menu_items();
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

export function hide_userlist_sidebar() {
    $(".app-main .column-right").removeClass("expanded");
}

export function show_userlist_sidebar() {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
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
function toggle_playground_link_popover(element, playground_info) {
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

export function register_click_handlers() {
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
            // We do the code extraction here and set the target href expanding
            // the url_template with the extracted code. Depending on whether
            // the language has multiple playground links configured, a popover
            // is shown.
            const extracted_code = $codehilite_div.find("code").text();
            if (playground_info.length === 1) {
                const url_template = url_template_lib.parse(playground_info[0].url_template);
                $view_in_playground_button.attr(
                    "href",
                    url_template.expand({code: extracted_code}),
                );
            } else {
                for (const $playground of playground_info) {
                    const url_template = url_template_lib.parse($playground.url_template);
                    $playground.playground_url = url_template.expand({code: extracted_code});
                }
                toggle_playground_link_popover(this, playground_info);
            }
        },
    );

    $("body").on("click", ".popover_playground_link", (e) => {
        hide_playground_links_popover();
        e.stopPropagation();
    });

    $("body").on("click", ".flatpickr-calendar", (e) => {
        e.stopPropagation();
        e.preventDefault();
    });

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
        stream_popover.is_open() ||
        user_group_popover.is_open() ||
        user_card_popover.user_sidebar_popped() ||
        user_card_popover.message_info_popped() ||
        user_card_popover.user_info_popped() ||
        emoji_picker.is_open() ||
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
    stream_popover.hide_stream_popover();
    user_group_popover.hide();
    user_card_popover.hide_all_user_info_popovers();
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
