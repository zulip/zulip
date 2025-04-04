import * as input_pill from "./input_pill.ts";
import {set_up_stream} from "./pill_typeahead.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_pill from "./stream_pill.ts";
import type {StreamPill} from "./stream_pill.ts";
import type {CombinedPill} from "./typeahead_helper.ts";

type SetUpPillTypeaheadConfig = {
    pill_widget: stream_pill.StreamPillWidget;
    $pill_container: JQuery;
};

function create_item_from_stream_name(
    stream_name: string,
    current_items: CombinedPill[],
): StreamPill | undefined {
    const stream_prefix_required = false;
    const get_allowed_streams = stream_data.get_invite_stream_data;
    const show_stream_sub_count = false;
    return stream_pill.create_item_from_stream_name(
        stream_name,
        current_items,
        stream_prefix_required,
        get_allowed_streams,
        show_stream_sub_count,
    );
}

function set_up_pill_typeahead({pill_widget, $pill_container}: SetUpPillTypeaheadConfig): void {
    const opts = {
        help_on_empty_strings: true,
        hide_on_empty_after_backspace: true,
        invite_streams: true,
    };
    set_up_stream($pill_container.find(".input"), pill_widget, opts);
}

export function add_default_stream_pills(pill_widget: stream_pill.StreamPillWidget): void {
    const default_stream_ids = stream_data.get_default_stream_ids();
    for (const stream_id of default_stream_ids) {
        const sub = stream_data.get_sub_by_id(stream_id);
        if (sub) {
            stream_pill.append_stream(sub, pill_widget, false);
        }
    }
}

export function create($stream_pill_container: JQuery): stream_pill.StreamPillWidget {
    const pill_widget = input_pill.create({
        $container: $stream_pill_container,
        create_item_from_text: create_item_from_stream_name,
        get_text_from_item: stream_pill.get_stream_name_from_item,
        generate_pill_html: stream_pill.generate_pill_html,
        get_display_value_from_item: stream_pill.get_display_value_from_item,
    });
    add_default_stream_pills(pill_widget);
    set_up_pill_typeahead({pill_widget, $pill_container: $stream_pill_container});
    return pill_widget;
}
