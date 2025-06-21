import assert from "minimalistic-assert";

import render_input_pill from "../templates/input_pill.hbs";

import type {InputPillContainer} from "./input_pill.ts";
import * as peer_data from "./peer_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import type {CombinedPill, CombinedPillContainer} from "./typeahead_helper.ts";

export type StreamPill = {
    type: "stream";
    stream_id: number;
    show_subscriber_count: boolean;
};

export type StreamPillWidget = InputPillContainer<StreamPill>;

export type StreamPillData = StreamSubscription & {type: "stream"};

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

export async function get_user_ids(
    pill_widget: StreamPillWidget | CombinedPillContainer,
): Promise<number[]> {
    const stream_ids = get_stream_ids(pill_widget);
    const results = await Promise.all(
        stream_ids.map(async (stream_id) => peer_data.get_all_subscribers(stream_id, true)),
    );

    const current_stream_ids_in_widget = get_stream_ids(pill_widget);
    let user_ids: number[] = [];
    for (const [index, stream_id] of stream_ids.entries()) {
        const subscribers = results[index]!;
        // Double check if the stream pill has been removed from the pill
        // widget while we were doing fetches.
        if (current_stream_ids_in_widget.includes(stream_id)) {
            user_ids = [...user_ids, ...subscribers];
        }
    }

    user_ids = [...new Set(user_ids)];
    user_ids.sort((a, b) => a - b);
    return user_ids;
}

export function get_display_value_from_item(item: StreamPill): string {
    const stream = stream_data.get_sub_by_id(item.stream_id);
    assert(stream !== undefined);
    return stream.name;
}

export function generate_pill_html(item: StreamPill): string {
    const stream = stream_data.get_sub_by_id(item.stream_id);
    assert(stream !== undefined);
    return render_input_pill({
        has_stream: true,
        stream,
        display_value: get_display_value_from_item(item),
        stream_id: item.stream_id,
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

    const active_streams = potential_streams.filter((sub) => !sub.is_archived);

    return filter_taken_streams(active_streams, pill_widget).map((stream) => ({
        ...stream,
        type: "stream",
    }));
}
