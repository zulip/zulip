import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import * as util from "./util";

let previous_pinned;
let previous_normal;
let previous_dormant;
let all_streams = [];

export function get_streams() {
    const sorted_streams = all_streams.map((stream_id) =>
        stream_data.maybe_get_stream_name(stream_id),
    );
    return sorted_streams;
}

function compare_function(a, b) {
    const stream_a = sub_store.get(a);
    const stream_b = sub_store.get(b);

    const stream_name_a = stream_a ? stream_a.name : "";
    const stream_name_b = stream_b ? stream_b.name : "";

    return util.strcmp(stream_name_a, stream_name_b);
}

export function sort_groups(streams, search_term) {
    const stream_id_to_name = (stream) => sub_store.get(stream).name;
    streams = util.filter_by_word_prefix_match(streams, search_term, stream_id_to_name);

    function is_normal(sub) {
        return stream_data.is_active(sub);
    }

    const pinned_streams = [];
    const normal_streams = [];
    const dormant_streams = [];

    for (const stream of streams) {
        const sub = sub_store.get(stream);
        const pinned = sub.pin_to_top;
        if (pinned) {
            pinned_streams.push(stream);
        } else if (is_normal(sub)) {
            normal_streams.push(stream);
        } else {
            dormant_streams.push(stream);
        }
    }

    pinned_streams.sort(compare_function);
    normal_streams.sort(compare_function);
    dormant_streams.sort(compare_function);

    const same_as_before =
        previous_pinned !== undefined &&
        util.array_compare(previous_pinned, pinned_streams) &&
        util.array_compare(previous_normal, normal_streams) &&
        util.array_compare(previous_dormant, dormant_streams);

    if (!same_as_before) {
        previous_pinned = pinned_streams;
        previous_normal = normal_streams;
        previous_dormant = dormant_streams;

        all_streams = pinned_streams.concat(normal_streams, dormant_streams);
    }

    return {
        same_as_before,
        pinned_streams,
        normal_streams,
        dormant_streams,
    };
}

function maybe_get_stream_id(i) {
    if (i < 0 || i >= all_streams.length) {
        return undefined;
    }

    return all_streams[i];
}

export function first_stream_id() {
    return maybe_get_stream_id(0);
}

export function prev_stream_id(stream_id) {
    const i = all_streams.indexOf(stream_id);

    if (i < 0) {
        return undefined;
    }

    return maybe_get_stream_id(i - 1);
}

export function next_stream_id(stream_id) {
    const i = all_streams.indexOf(stream_id);

    if (i < 0) {
        return undefined;
    }

    return maybe_get_stream_id(i + 1);
}
