import $ from "jquery";

import * as message_viewport from "./message_viewport";
import {user_settings} from "./user_settings";

let last_scroll_position = 0;

export function initialize() {
    set_layout_width();
}

export function disable_scrolling() {
    last_scroll_position = message_viewport.scrollTop();
    $("body").addClass("modal-open");
    $("#middle-container").css("top", `-${last_scroll_position}px`);
}

export function enable_scrolling() {
    $("body").removeClass("modal-open");
    $("#middle-container").css("top", `0px`);
    message_viewport.scrollTop(last_scroll_position);
}

export function set_layout_width() {
    if (user_settings.fluid_layout_width) {
        $(".header-main, .app .app-main, .fixed-app .app-main, #compose-container").css(
            "max-width",
            "inherit",
        );
    } else {
        $(".header-main, .app .app-main, .fixed-app .app-main, #compose-container").css(
            "max-width",
            "1400px",
        );
    }
}
