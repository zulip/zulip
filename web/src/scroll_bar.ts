import $ from "jquery";

import {user_settings} from "./user_settings";

export function set_layout_width(): void {
    if (user_settings.fluid_layout_width) {
        $("body").addClass("fluid_layout_width");
    } else {
        $("body").removeClass("fluid_layout_width");
    }
}

export function initialize(): void {
    set_layout_width();
}
