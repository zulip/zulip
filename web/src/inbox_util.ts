import $ from "jquery";

import type {Filter} from "./filter";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import assert from "minimalistic-assert";

let is_inbox_visible = false;
export let filter: Filter | undefined;

export function set_visible(value: boolean): void {
    is_inbox_visible = value;
}

export function set_filter(new_filter: Filter | undefined): void {
    if (new_filter !== undefined) {
        assert(new_filter.is_stream_only_narrow())
    }
    filter = new_filter;
}

export function current_filter(): Filter | undefined {
    return filter;
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
        if ($stream_privacy_icon.length) {
            $stream_privacy_icon.css("color", stream_color.get_stream_privacy_icon_color(color));
        }

        $stream_header.css("background", background_color);
    });
}
