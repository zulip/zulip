import * as tippy from "tippy.js";

import * as emoji_picker from "./emoji_picker";
import * as playground_links_popover from "./playground_links_popover";
import * as popover_menus from "./popover_menus";
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
        playground_links_popover.is_open()
    );
}

export function hide_all() {
    // Hides all tippy instances (tooltips and popovers).
    tippy.hideAll();
}
