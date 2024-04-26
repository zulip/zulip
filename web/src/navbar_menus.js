import {media_breakpoints_num} from "./css_variables";
import * as gear_menu from "./gear_menu";
import * as navbar_help_menu from "./navbar_help_menu";
import {page_params} from "./page_params";
import * as personal_menu_popover from "./personal_menu_popover";
import * as popover_menus from "./popover_menus";
import {
    hide_userlist_sidebar,
    right_sidebar_expanded_as_overlay,
    show_userlist_sidebar,
} from "./sidebar_ui";

// Available menu options based on user type
function getPopoverMenusOptions() {
    if (page_params.is_spectator) {
        return window.innerWidth < media_breakpoints_num.xl
            ? ["navbar_help_menu", "gear_menu", "login_button"]
            : ["signup_button", "login_button", "navbar_help_menu", "gear_menu"];
    }
    return ["navbar_help_menu", "gear_menu", "personal_menu"];
}

const popover_menus_options = getPopoverMenusOptions();

export function is_navbar_menus_displayed() {
    return (
        popover_menus.is_personal_menu_popover_displayed() ||
        popover_menus.is_gear_menu_popover_displayed() ||
        popover_menus.is_help_menu_popover_displayed()
    );
}

export function can_handle_navigation_hotkey() {
    return (
        document.activeElement &&
        (document.activeElement.classList.contains("signup_button") ||
            document.activeElement.classList.contains("login_button"))
    );
}

// Handle keyboard events for navigation
export function handle_keyboard_events(event_name) {
    const index = popover_menus_options.findIndex((menu) => is_menu_displayed(menu));

    if (index !== -1) {
        return handle_menu_event(popover_menus_options[index], event_name, index);
    }
    return false;
}
// Check if a specific menu is displayed
function is_menu_displayed(selected_popover_menu) {
    switch (selected_popover_menu) {
        case "signup_button":
            return document.activeElement.classList.contains("signup_button");
        case "login_button":
            return document.activeElement.classList.contains("login_button");
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
        case "user_list_toggle":
            if (!right_sidebar_expanded_as_overlay) {
                show_userlist_sidebar();
            } else if (right_sidebar_expanded_as_overlay) {
                hide_userlist_sidebar();
                navbar_help_menu.toggle();
            }
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

    // Toggle the focus state of a button
    function toggle_button_focus(selected_popover_menu) {
        if (window.innerWidth < media_breakpoints_num.xl) {
            const selected_element = document.querySelector(
                ".spectator_narrow_login_button ." + selected_popover_menu,
            );
            if (selected_element) {
                if (selected_element === document.activeElement) {
                    selected_element.blur();
                } else {
                    selected_element.focus();
                }
            }
        } else {
            const selected_element = document.querySelector("." + selected_popover_menu);
            if (document.activeElement.classList.contains(selected_popover_menu)) {
                selected_element.blur();
            } else {
                selected_element.focus();
            }
        }
    }
}
