import $ from "jquery";

import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";

let is_inbox_visible = false;

export const set_visible = (value: boolean): void => {
    is_inbox_visible = value;
};

export const is_visible = (): boolean => is_inbox_visible;

export const update_stream_colors = (): void => {
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
        $stream_header.css("background", background_color);
    });
};
