import $ from "jquery";

import * as gear_menu from "./gear_menu.ts";
import * as navbar_help_menu from "./navbar_help_menu.ts";
import * as personal_menu_popover from "./personal_menu_popover.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";

export function is_navbar_menus_displayed(): boolean {
    return (
        popover_menus.is_personal_menu_popover_displayed() ||
        popover_menus.is_gear_menu_popover_displayed() ||
        popover_menus.is_help_menu_popover_displayed()
    );
}

export function any_focused(): boolean {
    return $(".navbar-item:visible").is(":focus");
}

export function blur_focused(): void {
    if (any_focused()) {
        $(".navbar-item:visible").filter(":focus").trigger("blur");
    }
}

export function handle_keyboard_events(event_name: string): boolean {
    const allowed_events = new Set(["gear_menu", "left_arrow", "right_arrow"]);
    if (!allowed_events.has(event_name)) {
        return false;
    }

    if (event_name === "gear_menu") {
        blur_focused();
        gear_menu.toggle();
        return true;
    }
    const $current_navbar_menu = $(".navbar-item:visible").filter(".active-navbar-menu, :focus");
    const target_menu = get_target_navbar_menu(event_name, $current_navbar_menu);

    if (!target_menu) {
        return false;
    }
    return change_active_navbar_menu(target_menu);
}

function change_active_navbar_menu(target_menu: string): boolean {
    popovers.hide_all();
    blur_focused();
    switch (target_menu) {
        case "gear-menu":
            gear_menu.toggle();
            return true;
        case "help-menu":
            navbar_help_menu.toggle();
            return true;
        case "personal-menu":
            personal_menu_popover.toggle();
            return true;
        case "userlist-toggle-button":
        case "login_button":
            $(`#${target_menu}`).trigger("focus");
            return true;
        default:
            return false;
    }
}

function get_target_navbar_menu(
    event_name: string,
    $current_navbar_menu: JQuery,
): string | undefined {
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
