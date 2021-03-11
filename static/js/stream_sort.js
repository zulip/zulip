import {default as Fuse} from "fuse.js";

import * as stream_data from "./stream_data";
import * as util from "./util";

let previous_pinned;
let previous_normal;
let previous_dormant;
let all_streams = [];

export function get_streams() {
    // Right now this is only used for testing, but we should
    // use it for things like hotkeys that cycle through streams.
    const sorted_streams = all_streams.map((stream_id) =>
        stream_data.maybe_get_stream_name(stream_id),
    );
    return sorted_streams;
}

function filter_streams_by_search(streams, search_term) {
    if (search_term === "") {
        return streams;
    }

    const fuzzySearchOptions = {threshold: 0.5};
    const filtered_streams = new Fuse(
        streams.map((stream) => stream_data.get_sub_by_id(stream).name.toLowerCase()),
        fuzzySearchOptions,
    )
        .search(search_term.trim())
        .map((value) => streams[value.refIndex]);

    return filtered_streams;
}

export function sort_groups(streams, search_term) {
    if (streams.length === 0) {
        return undefined;
    }

    streams = filter_streams_by_search(streams, search_term);

    function is_normal(sub) {
        return stream_data.is_active(sub);
    }

    const pinned_streams = [];
    const normal_streams = [];
    const dormant_streams = [];

    for (const stream of streams) {
        const sub = stream_data.get_sub_by_id(stream);
        const pinned = sub.pin_to_top;
        if (pinned) {
            pinned_streams.push(stream);
        } else if (is_normal(sub)) {
            normal_streams.push(stream);
        } else {
            dormant_streams.push(stream);
        }
    }

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
