import $ from "jquery";
import {hideAll} from "tippy.js";

import * as emoji_picker from "./emoji_picker";
import * as overlays from "./overlays";
import * as playground_links_popover from "./playground_links_popover";
import * as popover_menus from "./popover_menus";
import * as right_sidebar_ui from "./right_sidebar_ui";
import * as stream_popover from "./stream_popover";
import * as user_card_popover from "./user_card_popover";
import * as user_group_popover from "./user_group_popover";

let list_of_popovers = [];

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

// On mobile web, opening the keyboard can trigger a resize event
// (which in turn can trigger a scroll event).  This will have the
// side effect of closing popovers, which we don't want.  So we
// suppress the first hide from scrolling after a resize using this
// variable.
let suppress_scroll_hide = false;

export function set_suppress_scroll_hide() {
    suppress_scroll_hide = true;
}

export function register_click_handlers() {
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
        user_card_popover.user_sidebar.is_open() ||
        user_card_popover.message_user_card.is_open() ||
        user_card_popover.user_card.is_open() ||
        emoji_picker.is_open() ||
        playground_links_popover.is_open() ||
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
    user_card_popover.hide_all_user_card_popovers();
    playground_links_popover.hide();

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
    right_sidebar_ui.hide_userlist_sidebar();
    stream_popover.hide_streamlist_sidebar();
    hide_all_except_sidebars({
        not_hide_tippy_instances,
    });
}

export function initialize() {
    overlays.register_pre_open_hook(hide_all);
    overlays.register_pre_close_hook(hide_all);
}
