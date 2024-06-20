import $ from "jquery";

import * as gear_menu from "./gear_menu";
import * as navbar_help_menu from "./navbar_help_menu";
import * as personal_menu_popover from "./personal_menu_popover";
import * as popover_menus from "./popover_menus";
import * as popovers from "./popovers";

export function is_navbar_menus_displayed() {
    return (
        popover_menus.is_personal_menu_popover_displayed() ||
        popover_menus.is_gear_menu_popover_displayed() ||
        popover_menus.is_help_menu_popover_displayed()
    );
}

export function any_focused() {
    return $(".navbar-item:visible").is(":focus");
}

export function blur_focused() {
    if (any_focused()) {
        $(".navbar-item:visible").filter(":focus").trigger("blur");
    }
}

export function handle_keyboard_events(event_name) {
    const allowed_events = new Set(["gear_menu", "left_arrow", "right_arrow"]);
    if (!allowed_events.has(event_name)) {
        return false;
    }

    if (event_name === "gear_menu") {
        blur_focused();
        gear_menu.toggle();
        return true;
    }
    const $current_navbar_menu = $(".navbar-item:visible").filter(".active, :focus");
    const $next_navbar_menu = get_next_navbar_menu(event_name, $current_navbar_menu);

    if (!$next_navbar_menu) {
        return false;
    }
    change_active_navbar_menu($current_navbar_menu, $next_navbar_menu);
    return true;
}

function change_active_navbar_menu($current_navbar_menu, $next_navbar_menu) {
    function toggle_menu($elt) {
        switch ($elt.attr("id")) {
            case "gear-menu":
                gear_menu.toggle();
                break;
            case "help-menu":
                navbar_help_menu.toggle();
                break;
            case "personal-menu":
                personal_menu_popover.toggle();
                break;
            case "userlist-toggle-button":
                if ($elt.is(":focus")) {
                    $elt.trigger("blur");
                } else {
                    $elt.trigger("focus");
                }
                popovers.hide_all();
                break;
        }
    }

    toggle_menu($current_navbar_menu);
    toggle_menu($next_navbar_menu);
}

function get_next_navbar_menu(event_name, $current_navbar_menu) {
    const $visible_navbar_menus = $(".navbar-item:visible");
    const index = $visible_navbar_menus.index($current_navbar_menu);
    let $next_navbar_menu;

    if (event_name === "left_arrow" && index === 0) {
        return undefined;
    } else if (event_name === "right_arrow" && index === $visible_navbar_menus.length - 1) {
        return undefined;
    }

    if (event_name === "left_arrow") {
        $next_navbar_menu = $visible_navbar_menus.eq(index - 1);
        return $next_navbar_menu;
    } else if (event_name === "right_arrow") {
        $next_navbar_menu = $visible_navbar_menus.eq(index + 1);
        return $next_navbar_menu;
    }
    return undefined;
}
