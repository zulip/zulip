import $ from "jquery";

import * as color_class from "./color_class";
import * as stream_data from "./stream_data";

function update_lock_icon_for_stream(stream_name) {
    const icon = $("#compose-lock-icon");
    const streamfield = $("#stream_message_recipient_stream");
    if (stream_data.get_invite_only(stream_name)) {
        icon.show();
        streamfield.addClass("lock-padding");
    } else {
        icon.hide();
        streamfield.removeClass("lock-padding");
    }
}


function update_globe_icon_for_stream(stream_name) {
    const icon = $("#compose-globe-icon");
    const streamfield = $("#stream_message_recipient_stream");
    if (stream_data.is_web_public(stream_name)) {
        icon.show();
        streamfield.addClass("globe-padding");
    } else {
        icon.hide();
        streamfield.removeClass("globe-padding");
    }
}


function update_hash_icon_for_stream(stream_name) {
    const icon = $("#compose-hash-icon");
    const streamfield = $("#stream_message_recipient_stream");
    if (stream_data.is_web_public(stream_name) || stream_data.get_invite_only(stream_name)) { 
        icon.hide();
        streamfield.removeClass("hash-padding");
    } else {
        icon.show();
        streamfield.addClass("hash-padding");
    }
}


// In an attempt to decrease mixing, set stream bar
// color look like the stream being used.
// (In particular, if there's a color associated with it,
//  have that color be reflected here too.)
export function decorate(stream_name, element, is_compose) {
    if (stream_name === undefined) {
        return;
    }
    const color = stream_data.get_color(stream_name);
    if (is_compose) {
        update_lock_icon_for_stream(stream_name);
        update_globe_icon_for_stream(stream_name);
        update_hash_icon_for_stream(stream_name);
    }
    element
        .css("background-color", color)
        .removeClass("dark_background")
        .addClass(color_class.get_css_class(color));
}
