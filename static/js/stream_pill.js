"use strict";

function display_pill(sub) {
    return "#" + sub.name + ": " + sub.subscriber_count + " users";
}

exports.create_item_from_stream_name = function (stream_name, current_items) {
    stream_name = stream_name.trim();
    if (!stream_name.startsWith("#")) {
        return;
    }
    stream_name = stream_name.substring(1);

    const sub = stream_data.get_sub(stream_name);
    if (!sub) {
        return;
    }

    const existing_ids = current_items.map((item) => item.stream_id);
    if (existing_ids.includes(sub.stream_id)) {
        return;
    }

    const item = {
        display_value: display_pill(sub),
        stream_id: sub.stream_id,
        stream_name: sub.name,
    };

    return item;
};

exports.get_stream_name_from_item = function (item) {
    return item.stream_name;
};

function get_user_ids_from_subs(items) {
    let user_ids = [];
    const stream_ids = items.map((item) => item.stream_id);
    for (const stream_id of stream_ids) {
        const sub = stream_data.get_sub_by_id(stream_id);
        if (!sub) {
            continue;
        }
        user_ids = user_ids.concat(sub.subscribers.map());
    }
    return user_ids;
}

exports.get_user_ids = function (pill_widget) {
    const items = pill_widget.items();
    let user_ids = get_user_ids_from_subs(items);
    user_ids = Array.from(new Set(user_ids));

    user_ids = user_ids.filter(Boolean);
    return user_ids;
};

exports.append_stream = function (stream, pill_widget) {
    pill_widget.appendValidatedData({
        display_value: display_pill(stream),
        stream_id: stream.stream_id,
        stream_name: stream.name,
    });
    pill_widget.clear_text();
};

exports.get_stream_ids = function (pill_widget) {
    const items = pill_widget.items();
    let stream_ids = items.map((item) => item.stream_id);
    stream_ids = stream_ids.filter(Boolean);

    return stream_ids;
};

exports.filter_taken_streams = function (items, pill_widget) {
    const taken_stream_ids = exports.get_stream_ids(pill_widget);
    items = items.filter((item) => !taken_stream_ids.includes(item.stream_id));
    return items;
};

exports.typeahead_source = function (pill_widget) {
    const potential_streams = stream_data.get_unsorted_subs();
    return exports.filter_taken_streams(potential_streams, pill_widget);
};

window.stream_pill = exports;
