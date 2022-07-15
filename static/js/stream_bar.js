import $ from "jquery";

import * as color_class from "./color_class";
import * as stream_data from "./stream_data";

function update_compose_stream_icon(stream_name) {
    const $globe_icon = $("#stream-message .compose-globe-icon");
    const $lock_icon = $("#stream-message .compose-lock-icon");
    const $hashtag = $("#stream-message .hashtag");
    // Reset state
    $globe_icon.hide();
    $lock_icon.hide();
    $hashtag.hide();

    if (stream_data.is_invite_only_by_stream_name(stream_name)) {
        $lock_icon.show();
    } else if (stream_data.is_web_public_by_stream_name(stream_name)) {
        $globe_icon.show();
    } else {
        $hashtag.show();
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
