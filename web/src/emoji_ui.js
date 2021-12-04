import $ from "jquery";

import {emoji_animation_config_values} from "./settings_config";
import {user_settings} from "./user_settings";

export function stop_animation($emoji) {
    if ($emoji.length) {
        const still_url = CSS.escape($emoji.attr("data-still-url"));
        if (still_url) {
            $emoji.attr("src", still_url);
        }
    }
}

export function animate($emoji) {
    if ($emoji.length) {
        const animated_url = CSS.escape($emoji.attr("data-animated-url"));
        if (animated_url) {
            $emoji.attr("src", animated_url);
        }
    }
}

// note that these mouse handlers need to be named functions in order to take
// advantage of how .addEventListener does not add the "same" listener a second
// time.
// An anonymous function would always be a different listener.
// see: https://developer.mozilla.org/en-US/docs/Web/API/EventTarget/addEventListener.
function handle_mouseenter_for_status_emoji_with_config(event) {
    if (user_settings.emoji_animation_config === emoji_animation_config_values.on_hover.code) {
        handle_mouseenter_for_status_emoji(event);
    }
}

function handle_mouseleave_for_status_emoji_with_config(event) {
    if (user_settings.emoji_animation_config === emoji_animation_config_values.on_hover.code) {
        handle_mouseleave_for_status_emoji(event);
    }
}

function handle_mouseenter_for_status_emoji(event) {
    const $animatable_status_emoji = $(event.target).find("img.status_emoji[data-still-url]");
    animate($animatable_status_emoji);
}

export function handle_mouseleave_for_status_emoji(event) {
    const $animatable_status_emoji = $(event.target).find("img.status_emoji[data-still-url]");
    stop_animation($animatable_status_emoji);
}

// These functions expects DOM elements, it will not work if passed jquery elements!
export function bind_handlers_for_status_emoji(elem) {
    if ($(elem).find("img.status_emoji[data-still-url]").length > 0) {
        elem.addEventListener("mouseenter", handle_mouseenter_for_status_emoji);
        elem.addEventListener("mouseleave", handle_mouseleave_for_status_emoji);
    }
}

export function bind_config_based_status_emoji_handlers(elem) {
    if ($(elem).find("img.status_emoji[data-still-url]").length > 0) {
        elem.addEventListener("mouseenter", handle_mouseenter_for_status_emoji_with_config);
        elem.addEventListener("mouseleave", handle_mouseleave_for_status_emoji_with_config);
    }
}
