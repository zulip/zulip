import $ from "jquery";

// exported for testing
export function stop_animation($emoji) {
    if ($emoji.length) {
        const still_url = CSS.escape($emoji.attr("data-still-url"));
        if (still_url) {
            $emoji.attr("src", still_url);
        }
    }
}

// exported for testing
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
export function handle_mouseenter_for_status_emoji(event) {
    const $animatable_status_emoji = $(event.target).find("img.status_emoji[data-still-url]");
    animate($animatable_status_emoji);
}

export function handle_mouseleave_for_status_emoji(event) {
    const $animatable_status_emoji = $(event.target).find("img.status_emoji[data-still-url]");
    stop_animation($animatable_status_emoji);
}

// This function expects DOM elements, it will not work if passed jquery elements!
export function bind_handlers_for_status_emoji(elem) {
    if ($(elem).find("img.status_emoji[data-still-url]").length > 0) {
        elem.addEventListener("mouseenter", handle_mouseenter_for_status_emoji);
        elem.addEventListener("mouseleave", handle_mouseleave_for_status_emoji);
    }
}
