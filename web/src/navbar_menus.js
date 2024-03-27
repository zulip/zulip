import $ from "jquery";

import * as gear_menu from "./gear_menu";
import * as navbar_help_menu from "./navbar_help_menu";
import {page_params} from "./page_params";
import * as personal_menu_popover from "./personal_menu_popover";
import * as popover_menus from "./popover_menus";

// Available menu options based on user type
const popover_menus_options = page_params.is_spectator
    ? ["signup_button", "login_button", "navbar_help_menu", "gear_menu"]
    : ["navbar_help_menu", "gear_menu", "personal_menu"];

export function is_navbar_menus_displayed() {
    return (
        popover_menus.is_personal_menu_popover_displayed() ||
        popover_menus.is_gear_menu_popover_displayed() ||
        popover_menus.is_help_menu_popover_displayed()
    );
}

// Handle keyboard events for navigation
export function handle_keyboard_events(event_name) {
    let i = 0;
    for (const selected_popover of popover_menus_options) {
        if (is_menu_displayed(selected_popover)) {
            return handle_menu_event(selected_popover, event_name, i);
        }
        i = i + 1;
    }

    return false;
}

// Check if a specific menu is displayed
function is_menu_displayed(selected_popover_menu) {
    switch (selected_popover_menu) {
        case "signup_button":
            return document.activeElement.className === "signup_button";
        case "login_button":
            return document.activeElement.className === "login_button";
        case "navbar_help_menu":
            return popover_menus.is_help_menu_popover_displayed();
        case "gear_menu":
            return popover_menus.is_gear_menu_popover_displayed();
        case "personal_menu":
            return popover_menus.is_personal_menu_popover_displayed();
    }
    return false;
}

// Handle navigation events for specific menus
function handle_menu_event(selected_popover_menu, event_name, index) {
    switch (event_name) {
        case "gear_menu":
            toggle_menu(selected_popover_menu);
            return true;
        case "left_arrow":
            if (index > 0) {
                toggle_menu(selected_popover_menu);
                toggle_menu(popover_menus_options[index - 1]);
                return true;
            }
            break;
        case "right_arrow":
            if (index < popover_menus_options.length - 1) {
                toggle_menu(selected_popover_menu);
                toggle_menu(popover_menus_options[index + 1]);
                return true;
            }
            break;
    }
    return false;
}

// Toggle the display state of a specific menu
function toggle_menu(selected_popover_menu) {
    switch (selected_popover_menu) {
        case "signup_button":
        case "login_button":
            toggle_button_focus(selected_popover_menu);
            break;
        case "navbar_help_menu":
            navbar_help_menu.toggle();
            break;
        case "gear_menu":
            gear_menu.toggle();
            break;
        case "personal_menu":
            personal_menu_popover.toggle();
            break;
    }
}

// Toggle the focus state of a button
function toggle_button_focus(selected_popover_menu) {
    const $selected_navbar_option = $("." + selected_popover_menu);
    if ($selected_navbar_option.is(":focus")) {
        $selected_navbar_option.trigger("blur");
    } else {
        $selected_navbar_option.trigger("focus");
    }
}
