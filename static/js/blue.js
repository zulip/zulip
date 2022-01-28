import $ from "jquery";

let enabled = false;
let recent_hotkey_usage = false;

export function is_enabled() {
    return enabled;
}

export function hotkey() {
    recent_hotkey_usage = true;
}

export function enable() {
    $(".message_list").addClass("enable_selections");
    enabled = true;
}

export function disable() {
    $(".message_list").removeClass("enable_selections");
    enabled = false;
}

export function maybe_disable() {
    if (recent_hotkey_usage) {
        recent_hotkey_usage = false;
        return;
    }
    $(".message_list").removeClass("enable_selections");
    enabled = false;
}
