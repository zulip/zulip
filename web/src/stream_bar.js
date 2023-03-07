import $ from "jquery";

import * as color_class from "./color_class";
import * as stream_data from "./stream_data";

function update_compose_stream_icon(stream_name) {
    const $streamfield = $("#stream_message_recipient_stream");
    const $globe_icon = $("#compose-globe-icon");
    const $lock_icon = $("#compose-lock-icon");

    // Reset state
    $globe_icon.hide();
    $lock_icon.hide();
    $streamfield.removeClass("lock-padding");

    if (stream_data.is_invite_only_by_stream_name(stream_name)) {
        $lock_icon.show();
        $streamfield.addClass("lock-padding");
    } else if (stream_data.is_web_public_by_stream_name(stream_name)) {
        $globe_icon.show();
        $streamfield.addClass("lock-padding");
    }
}

// In an attempt to decrease mixing, set stream bar
// color look like the stream being used.
// (In particular, if there's a color associated with it,
//  have that color be reflected here too.)
export function decorate(stream_name, $element, is_compose) {
    if (stream_name === undefined) {
        return;
    }
    const color = stream_data.get_color(stream_name);
    if (is_compose) {
        update_compose_stream_icon(stream_name);
    }
    $element
        .css("background-color", color)
        .removeClass("dark_background")
        .addClass(color_class.get_css_class(color));
}
