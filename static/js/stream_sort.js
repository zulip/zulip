const util = require("./util");
let previous_pinned;
let previous_normal;
let previous_dormant;
let all_streams = [];

exports.get_streams = function () {
    // Right now this is only used for testing, but we should
    // use it for things like hotkeys that cycle through streams.
    return all_streams;
};

function filter_streams_by_search(streams, search_term) {
    if (search_term === '') {
        return streams;
    }

    let search_terms = search_term.toLowerCase().split(",");
    search_terms = search_terms.map(s => s.trim());

    const filtered_streams = streams.filter(stream => search_terms.some(search_term => {
        const lower_stream_name = stream.toLowerCase();
        const cands = lower_stream_name.split(" ");
        cands.push(lower_stream_name);
        return cands.some(name => name.startsWith(search_term));
    }));

    return filtered_streams;
}

exports.sort_groups = function (streams, search_term) {
    if (streams.length === 0) {
        return;
    }

    streams = filter_streams_by_search(streams, search_term);

    function is_normal(sub) {
        return stream_data.is_active(sub);
    }

    const pinned_streams = [];
    const normal_streams = [];
    const dormant_streams = [];

    for (const stream of streams) {
        const sub = stream_data.get_sub(stream);
        const pinned = sub.pin_to_top;
        if (pinned) {
            pinned_streams.push(stream);
        } else if (is_normal(sub)) {
            normal_streams.push(stream);
        } else {
            dormant_streams.push(stream);
        }
    }

    pinned_streams.sort(util.strcmp);
    normal_streams.sort(util.strcmp);
    dormant_streams.sort(util.strcmp);

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
        same_as_before: same_as_before,
        pinned_streams: pinned_streams,
        normal_streams: normal_streams,
        dormant_streams: dormant_streams,
    };
};

function pos(stream_id) {
    const sub = stream_data.get_sub_by_id(stream_id);
    const name = sub.name;
    const i = all_streams.indexOf(name);

    if (i < 0) {
        return;
    }

    return i;
}

function maybe_get_stream_id(i) {
    if (i < 0 || i >= all_streams.length) {
        return;
    }

    const name = all_streams[i];
    const stream_id = stream_data.get_stream_id(name);
    return stream_id;
}

exports.first_stream_id = function () {
    return maybe_get_stream_id(0);
};

exports.prev_stream_id = function (stream_id) {
    const i = pos(stream_id);

    if (i === undefined) {
        return;
    }

    return maybe_get_stream_id(i - 1);
};

exports.next_stream_id = function (stream_id) {
    const i = pos(stream_id);

    if (i === undefined) {
        return;
    }

    return maybe_get_stream_id(i + 1);
};

window.stream_sort = exports;
