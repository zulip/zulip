import $ from "jquery";

function stop_animation($emoji) {
    if ($emoji.length) {
        const still_url = CSS.escape($emoji.attr("data-still-url"));
        if (still_url) {
            $emoji.attr("src", still_url);
        }
    }
}

function animate($emoji) {
    if ($emoji.length) {
        const animated_url = CSS.escape($emoji.attr("data-animated-url"));
        if (animated_url) {
            $emoji.attr("src", animated_url);
        }
    }
}

export function handle_mouseenter_for_status_emoji(event) {
    const $status_emoji = $(event.target).closest(".user_sidebar_entry").find("img.status_emoji");
    animate($status_emoji);
}

export function handle_mouseleave_for_status_emoji(event) {
    const $status_emoji = $(event.target).closest(".user_sidebar_entry").find("img.status_emoji");
    stop_animation($status_emoji);
}
