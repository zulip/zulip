import * as input_pill from "./input_pill";
import {set_up} from "./pill_typeahead";
import * as stream_data from "./stream_data";
import * as stream_pill from "./stream_pill";
import type {StreamSubscription} from "./sub_store";

type CreateConfig = {
    $pill_container: JQuery;
    get_invite_streams: () => stream_data.InviteStreamData[];
};

type SetUpPillTypeaheadConfig = {
    pill_widget: stream_pill.StreamPillWidget;
    $pill_container: JQuery;
};

function display_pill(sub: StreamSubscription): string {
    return "#" + sub.name;
}

function create_item_from_text(
    stream_name: string,
    current_items: input_pill.InputPillItem<stream_pill.StreamPill>[],
): input_pill.InputPillItem<stream_pill.StreamPill> | undefined {
    stream_name = stream_name.trim();
    const sub = stream_data.get_sub(stream_name);
    if (!sub) {
        return undefined;
    }
    const existing_ids = current_items.map((item) => item.stream_id);
    if (existing_ids.includes(sub.stream_id)) {
        return undefined;
    }
    const item = {
        type: "stream",
        display_value: sub.name,
        stream_id: sub.stream_id,
        stream_name: sub.name,
    };
    return item;
}

function get_text_from_item(item: input_pill.InputPillItem<stream_pill.StreamPill>): string {
    const text = stream_pill.get_stream_name_from_item(item);
    if (text) {
        return text;
    }
    return "";
}

function set_up_pill_typeahead({pill_widget, $pill_container}: SetUpPillTypeaheadConfig): void {
    const opts = {
        stream: true,
        user_group: false,
        user: false,
        exclude_bots: true,
        help_on_empty_strings: true,
        display_pill,
    };
    set_up($pill_container.find(".input"), pill_widget, opts);
}

function add_default_stream_pills(
    pill_widget: stream_pill.StreamPillWidget,
    streams: stream_data.InviteStreamData[],
): void {
    for (const stream of streams) {
        if (stream.default_stream) {
            const sub = stream_data.get_sub(stream.name);
            if (sub) {
                stream_pill.append_stream(sub, pill_widget, display_pill);
            }
        }
    }
}

export function create(config: CreateConfig): stream_pill.StreamPillWidget {
    const pill_widget = input_pill.create({
        $container: config.$pill_container,
        create_item_from_text,
        get_text_from_item,
    });
    const streams = config.get_invite_streams();
    add_default_stream_pills(pill_widget, streams);
    set_up_pill_typeahead({pill_widget, $pill_container: config.$pill_container});
    return pill_widget;
}
