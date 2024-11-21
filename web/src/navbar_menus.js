import $ from "jquery";

import * as gear_menu from "./gear_menu.js";
import * as navbar_help_menu from "./navbar_help_menu.ts";
import {page_params} from "./page_params.ts";
import * as personal_menu_popover from "./personal_menu_popover.ts";
import * as popover_menus from "./popover_menus.ts";

export function is_navbar_menus_displayed() {
    return (
        popover_menus.is_personal_menu_popover_displayed() ||
        popover_menus.is_gear_menu_popover_displayed() ||
        popover_menus.is_help_menu_popover_displayed()
    );
}

export function handle_keyboard_events(event_name) {
    const allowed_events = new Set(["gear_menu", "left_arrow", "right_arrow"]);
    if (!allowed_events.has(event_name)) {
        return false;
    }

    if (event_name === "gear_menu") {
        gear_menu.toggle();
        return true;
    }
    const $current_navbar_menu = $(".navbar-item:visible").filter(".active-navbar-menu");
    const target_menu = get_target_navbar_menu(event_name, $current_navbar_menu);

    if (!target_menu) {
        return false;
    }
    return change_active_navbar_menu(target_menu);
}

function change_active_navbar_menu(target_menu) {
    // We don't need to process arrow keys in navbar menus for spectators
    // since they only have gear menu present.
    if (
        popover_menus.is_personal_menu_popover_displayed() &&
        target_menu === "gear-menu" &&
        !page_params.is_spectator
    ) {
        // Open gear menu popover on left arrow.
        personal_menu_popover.toggle();
        gear_menu.toggle();
        return true;
    }

    if (popover_menus.is_help_menu_popover_displayed() && target_menu === "gear-menu") {
        // Open gear menu popover on right arrow.
        navbar_help_menu.toggle();
        gear_menu.toggle();
        return true;
    }

    if (popover_menus.is_gear_menu_popover_displayed()) {
        if (target_menu === "gear-menu") {
            gear_menu.toggle();
            return true;
        } else if (target_menu === "personal-menu" && !page_params.is_spectator) {
            // Open personal menu popover on g + right arrow.
            gear_menu.toggle();
            personal_menu_popover.toggle();
            return true;
        } else if (target_menu === "help-menu") {
            // Open help menu popover on g + left arrow.
            gear_menu.toggle();
            navbar_help_menu.toggle();
            return true;
        }
    }

    return false;
}

function get_target_navbar_menu(event_name, $current_navbar_menu) {
    const $visible_navbar_menus = $(".navbar-item:visible");
    const index = $visible_navbar_menus.index($current_navbar_menu);
    let $target_navbar_menu;

    if (event_name === "left_arrow" && index === 0) {
        return undefined;
    } else if (event_name === "right_arrow" && index === $visible_navbar_menus.length - 1) {
        return undefined;
    }

    if (event_name === "left_arrow") {
        $target_navbar_menu = $visible_navbar_menus.eq(index - 1);
        return $target_navbar_menu.attr("id");
    } else if (event_name === "right_arrow") {
        $target_navbar_menu = $visible_navbar_menus.eq(index + 1);
        return $target_navbar_menu.attr("id");
    }
    return undefined;
}
