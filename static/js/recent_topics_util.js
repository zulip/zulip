import $ from "jquery";

import * as compose_state from "./compose_state";
import * as overlays from "./overlays";
import * as popovers from "./popovers";

let is_rt_visible = false;

export function set_visible(value) {
    is_rt_visible = value;
}

export function is_visible() {
    return is_rt_visible;
}

export function is_in_focus() {
    // Check if user is focused on
    // recent topics.
    return (
        is_visible() &&
        !compose_state.composing() &&
        !popovers.any_active() &&
        !overlays.is_active() &&
        !overlays.is_modal_open() &&
        !$(".home-page-input").is(":focus")
    );
}

export function get_topic_key(stream_id, topic) {
    return stream_id + ":" + topic.toLowerCase();
}
