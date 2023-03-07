import * as peer_data from "./peer_data";
import * as stream_data from "./stream_data";

function display_pill(sub) {
    const sub_count = peer_data.get_subscriber_count(sub.stream_id);
    return "#" + sub.name + ": " + sub_count + " users";
}

export function create_item_from_stream_name(stream_name, current_items) {
    stream_name = stream_name.trim();
    if (!stream_name.startsWith("#")) {
        return undefined;
    }
    stream_name = stream_name.slice(1);

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
        display_value: display_pill(sub),
        stream_id: sub.stream_id,
        stream_name: sub.name,
    };

    return item;
}

export function get_stream_name_from_item(item) {
    return item.stream_name;
}

function get_user_ids_from_subs(items) {
    let user_ids = [];
    for (const item of items) {
        // only some of our items have streams (for copy-from-stream)
        if (item.stream_id !== undefined) {
            user_ids = [...user_ids, ...peer_data.get_subscribers(item.stream_id)];
        }
    }
    return user_ids;
}

export function get_user_ids(pill_widget) {
    const items = pill_widget.items();
    let user_ids = get_user_ids_from_subs(items);
    user_ids = [...new Set(user_ids)];

    user_ids = user_ids.filter(Boolean);
    user_ids.sort((a, b) => a - b);
    return user_ids;
}

export function append_stream(stream, pill_widget) {
    pill_widget.appendValidatedData({
        type: "stream",
        display_value: display_pill(stream),
        stream_id: stream.stream_id,
        stream_name: stream.name,
    });
    pill_widget.clear_text();
}

export function get_stream_ids(pill_widget) {
    const items = pill_widget.items();
    let stream_ids = items.map((item) => item.stream_id);
    stream_ids = stream_ids.filter(Boolean);

    return stream_ids;
}

export function filter_taken_streams(items, pill_widget) {
    const taken_stream_ids = get_stream_ids(pill_widget);
    items = items.filter((item) => !taken_stream_ids.includes(item.stream_id));
    return items;
}

export function typeahead_source(pill_widget) {
    const potential_streams = stream_data.get_unsorted_subs();
    return filter_taken_streams(potential_streams, pill_widget);
}
