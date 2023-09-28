import $ from "jquery";
import {hideAll} from "tippy.js";

import * as emoji_picker from "./emoji_picker";
import * as playground_links_popover from "./playground_links_popover";
import * as popover_menus from "./popover_menus";
import * as sidebar_ui from "./sidebar_ui";
import * as stream_popover from "./stream_popover";
import * as user_card_popover from "./user_card_popover";
import * as user_group_popover from "./user_group_popover";

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
}

// This function will hide all the popovers, including the mobile web
// or narrow window sidebars.
export function hide_all(not_hide_tippy_instances) {
    sidebar_ui.hide_userlist_sidebar();
    sidebar_ui.hide_streamlist_sidebar();
    hide_all_except_sidebars({
        not_hide_tippy_instances,
    });
}
