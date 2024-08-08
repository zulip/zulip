import assert from "minimalistic-assert";

import render_input_pill from "../templates/input_pill.hbs";

import {$t} from "./i18n";
import type {InputPillContainer} from "./input_pill";
import * as peer_data from "./peer_data";
import * as stream_data from "./stream_data";
import type {StreamSubscription} from "./sub_store";
import type {CombinedPill, CombinedPillContainer} from "./typeahead_helper";

export type StreamPill = {
    type: "stream";
    stream_id: number;
    show_subscriber_count: boolean;
};

export type StreamPillWidget = InputPillContainer<StreamPill>;

export type StreamPillData = StreamSubscription & {type: "stream"};

function format_stream_name_and_subscriber_count(sub: StreamSubscription): string {
    const sub_count = peer_data.get_subscriber_count(sub.stream_id);
    return $t(
        {defaultMessage: "{stream_name}: {sub_count} users"},
        {stream_name: sub.name, sub_count},
    );
}

export function create_item_from_stream_name(
    stream_name: string,
    current_items: CombinedPill[],
    stream_prefix_required = true,
    get_allowed_streams: () => StreamSubscription[] = stream_data.get_unsorted_subs,
    show_subscriber_count = true,
): StreamPill | undefined {
    stream_name = stream_name.trim();
    if (stream_prefix_required) {
        if (!stream_name.startsWith("#")) {
            return undefined;
        }
        stream_name = stream_name.slice(1);
    }

    const sub = stream_data.get_sub(stream_name);
    if (!sub) {
        return undefined;
    }

    const streams = get_allowed_streams();
    if (!streams.includes(sub)) {
        return undefined;
    }

    if (current_items.some((item) => item.type === "stream" && item.stream_id === sub.stream_id)) {
        return undefined;
    }

    return {
        type: "stream",
        show_subscriber_count,
        stream_id: sub.stream_id,
    };
}

export function get_stream_name_from_item(item: StreamPill): string {
    const stream = stream_data.get_sub_by_id(item.stream_id);
    assert(stream !== undefined);
    return stream.name;
}

export function get_user_ids(pill_widget: StreamPillWidget | CombinedPillContainer): number[] {
    let user_ids = pill_widget
        .items()
        .flatMap((item) =>
            item.type === "stream" ? peer_data.get_subscribers(item.stream_id) : [],
        );
    user_ids = [...new Set(user_ids)];
    user_ids.sort((a, b) => a - b);
    return user_ids;
}

export function get_display_value_from_item(item: StreamPill): string {
    const stream = stream_data.get_sub_by_id(item.stream_id);
    assert(stream !== undefined);
    if (item.show_subscriber_count) {
        return format_stream_name_and_subscriber_count(stream);
    }
    return stream.name;
}

export function generate_pill_html(item: StreamPill): string {
    const stream = stream_data.get_sub_by_id(item.stream_id);
    assert(stream !== undefined);
    return render_input_pill({
        has_stream: true,
        stream,
        display_value: get_display_value_from_item(item),
    });
}

export function append_stream(
    stream: StreamSubscription,
    pill_widget: StreamPillWidget | CombinedPillContainer,
    show_subscriber_count = true,
): void {
    pill_widget.appendValidatedData({
        type: "stream",
        show_subscriber_count,
        stream_id: stream.stream_id,
    });
    pill_widget.clear_text();
}

export function get_stream_ids(pill_widget: StreamPillWidget | CombinedPillContainer): number[] {
    const items = pill_widget.items();
    return items.flatMap((item) => (item.type === "stream" ? item.stream_id : []));
}

export function filter_taken_streams(
    items: StreamSubscription[],
    pill_widget: StreamPillWidget | CombinedPillContainer,
): StreamSubscription[] {
    const taken_stream_ids = get_stream_ids(pill_widget);
    items = items.filter((item) => !taken_stream_ids.includes(item.stream_id));
    return items;
}

export function typeahead_source(
    pill_widget: StreamPillWidget | CombinedPillContainer,
    invite_streams?: boolean,
): StreamPillData[] {
    const potential_streams = invite_streams
        ? stream_data.get_invite_stream_data()
        : stream_data.get_unsorted_subs();
    return filter_taken_streams(potential_streams, pill_widget).map((stream) => ({
        ...stream,
        type: "stream",
    }));
}
