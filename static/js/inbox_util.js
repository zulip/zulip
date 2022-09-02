import chroma from "chroma-js";
import $ from "jquery";

import * as compose_state from "./compose_state";
import * as overlays from "./overlays";
import * as popovers from "./popovers";
import * as settings_data from "./settings_data";

let is_inbox_visible = false;

export function set_visible(value) {
    is_inbox_visible = value;
}

export function is_visible() {
    return is_inbox_visible;
}

export function get_pm_key(msg) {
    return "pm:" + msg.other_user_id;
}

export function is_in_focus() {
    // Check if user is focused on
    // inbox
    return (
        is_visible() &&
        !compose_state.composing() &&
        !popovers.any_active() &&
        !overlays.is_overlay_or_modal_open() &&
        !$(".home-page-input").is(":focus")
    );
}

export function correct_stream_color(color) {
    const color_l = chroma(color).get("lch.l");
    const min_color_l = 20;
    const max_color_l = 75;
    if (color_l < min_color_l) {
        return chroma(color).set("lch.l", min_color_l).hex();
    } else if (color_l > max_color_l) {
        return chroma(color).set("lch.l", max_color_l).hex();
    }
    return color;
}

export function get_stream_header_color(color) {
    const using_dark_theme = settings_data.using_dark_theme();
    return chroma.mix(color, using_dark_theme ? "black" : "white", 0.8, "rgb").hex();
}

export function get_pm_header_color() {
    const using_dark_theme = settings_data.using_dark_theme();
    return using_dark_theme ? "#403A26" : "#f3f0e7";
}
