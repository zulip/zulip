import $ from "jquery";

import {user_settings} from "./user_settings";

export function set_layout_width(): void {
    if (user_settings.fluid_layout_width) {
        $(".header-main, .app .app-main, #compose-container").css("max-width", "inherit");
    } else {
        $(".header-main, .app .app-main, #compose-container").css("max-width", "1400px");
    }
}

export function initialize(): void {
    set_layout_width();
}
