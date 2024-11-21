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
    return change_active_navbar_menu(event_name);
}

function change_active_navbar_menu(event_name) {
    // We don't need to process arrow keys in navbar menus for spectators
    // since they only have gear menu present.
    if (
        popover_menus.is_personal_menu_popover_displayed() &&
        (event_name === "left_arrow" || event_name === "gear_menu") &&
        !page_params.is_spectator
    ) {
        // Open gear menu popover on left arrow.
        personal_menu_popover.toggle();
        gear_menu.toggle();
        return true;
    }

    if (
        popover_menus.is_help_menu_popover_displayed() &&
        (event_name === "right_arrow" || event_name === "gear_menu")
    ) {
        // Open gear menu popover on right arrow.
        navbar_help_menu.toggle();
        gear_menu.toggle();
        return true;
    }

    if (popover_menus.is_gear_menu_popover_displayed()) {
        if (event_name === "gear_menu") {
            gear_menu.toggle();
            return true;
        } else if (event_name === "right_arrow" && !page_params.is_spectator) {
            // Open personal menu popover on g + right arrow.
            gear_menu.toggle();
            personal_menu_popover.toggle();
            return true;
        } else if (event_name === "left_arrow") {
            // Open help menu popover on g + left arrow.
            gear_menu.toggle();
            navbar_help_menu.toggle();
            return true;
        }
    }

    return false;
}
