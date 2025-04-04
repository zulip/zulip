import $ from "jquery";

import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";

let is_inbox_visible = false;

export function set_visible(value: boolean): void {
    is_inbox_visible = value;
}

export function is_visible(): boolean {
    return is_inbox_visible;
}

export function update_stream_colors(): void {
    if (!is_visible()) {
        return;
    }

    const $stream_headers = $("#inbox-streams-container .inbox-header");
    $stream_headers.each((_index, stream_header) => {
        const $stream_header = $(stream_header);
        const stream_id = Number.parseInt($stream_header.attr("data-stream-id")!, 10);
        if (!stream_id) {
            return;
        }
        const color = stream_data.get_color(stream_id);
        const background_color = stream_color.get_recipient_bar_color(color);

        const $stream_privacy_icon = $stream_header.find(".stream-privacy");
        if ($stream_privacy_icon.length > 0) {
            $stream_privacy_icon.css("color", stream_color.get_stream_privacy_icon_color(color));
        }

        $stream_header.css("background", background_color);
    });
}
