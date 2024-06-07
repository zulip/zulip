import type {InputPillContainer, InputPillItem} from "./input_pill";
import * as peer_data from "./peer_data";
import * as stream_data from "./stream_data";
import type {StreamSubscription} from "./sub_store";
import type {CombinedPillContainer, CombinedPillItem} from "./typeahead_helper";

export type StreamPill = {
    type: "stream";
    stream_id: number;
    stream_name: string;
};

type StreamPillWidget = InputPillContainer<StreamPill>;

export type StreamPillData = StreamSubscription & {type: "stream"};

const display_pill = (sub: StreamSubscription): string => {
    const sub_count = peer_data.get_subscriber_count(sub.stream_id);
    return "#" + sub.name + ": " + sub_count + " users";
};

export const create_item_from_stream_name = (
    stream_name: string,
    current_items: CombinedPillItem[],
): InputPillItem<StreamPill> | undefined => {
    stream_name = stream_name.trim();
    if (!stream_name.startsWith("#")) {
        return undefined;
    }
    stream_name = stream_name.slice(1);

    const sub = stream_data.get_sub(stream_name);
    if (!sub) {
        return undefined;
    }

    if (current_items.some((item) => item.type === "stream" && item.stream_id === sub.stream_id)) {
        return undefined;
    }

    return {
        type: "stream",
        display_value: display_pill(sub),
        stream_id: sub.stream_id,
        stream_name: sub.name,
    };
};

export const get_stream_name_from_item = (item: InputPillItem<StreamPill>): string =>
    item.stream_name;

export const get_user_ids = (pill_widget: StreamPillWidget | CombinedPillContainer): number[] => {
    let user_ids = pill_widget
        .items()
        .flatMap((item) =>
            item.type === "stream" ? peer_data.get_subscribers(item.stream_id) : [],
        );
    user_ids = [...new Set(user_ids)];
    user_ids.sort((a, b) => a - b);
    return user_ids;
};

export const append_stream = (
    stream: StreamSubscription,
    pill_widget: CombinedPillContainer,
): void => {
    pill_widget.appendValidatedData({
        type: "stream",
        display_value: display_pill(stream),
        stream_id: stream.stream_id,
        stream_name: stream.name,
    });
    pill_widget.clear_text();
};

export const get_stream_ids = (pill_widget: CombinedPillContainer): number[] => {
    const items = pill_widget.items();
    return items.flatMap((item) => (item.type === "stream" ? item.stream_id : []));
};

export const filter_taken_streams = (
    items: StreamSubscription[],
    pill_widget: CombinedPillContainer,
): StreamSubscription[] => {
    const taken_stream_ids = get_stream_ids(pill_widget);
    items = items.filter((item) => !taken_stream_ids.includes(item.stream_id));
    return items;
};

export const typeahead_source = (pill_widget: CombinedPillContainer): StreamPillData[] => {
    const potential_streams = stream_data.get_unsorted_subs();
    return filter_taken_streams(potential_streams, pill_widget).map((stream) => ({
        ...stream,
        type: "stream",
    }));
};
