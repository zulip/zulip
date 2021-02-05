"use strict";

const peer_data = require("./peer_data");

function display_pill(sub) {
    const sub_count = peer_data.get_subscriber_count(sub.stream_id);
    return "#" + sub.name + ": " + sub_count + " users";
}

exports.create_item_from_stream_name = function (stream_name, current_items) {
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
    for (const item of items) {
        // only some of our items have streams (for copy-from-stream)
        if (item.stream_id !== undefined) {
            user_ids = user_ids.concat(peer_data.get_subscribers(item.stream_id));
        }
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
