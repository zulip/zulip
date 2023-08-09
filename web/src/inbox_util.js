import $ from "jquery";

import * as compose_state from "./compose_state";
import * as overlays from "./overlays";
import * as popovers from "./popovers";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";

let is_inbox_visible = false;

export function set_visible(value) {
    is_inbox_visible = value;
}

export function is_visible() {
    return is_inbox_visible;
}

export function get_dm_key(msg) {
    return "dm:" + msg.other_user_id;
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

export function update_stream_colors() {
    if (!is_visible()) {
        return;
    }

    const $stream_headers = $("#inbox-streams-container .inbox-header");
    $stream_headers.each((_index, stream_header) => {
        const $stream_header = $(stream_header);
        const stream_id = Number.parseInt($stream_header.attr("data-stream-id"), 10);
        if (!stream_id) {
            return;
        }
        const color = stream_data.get_color(stream_id);
        const background_color = stream_color.get_recipient_bar_color(color);
        $stream_header.css("background", background_color);
    });
}
