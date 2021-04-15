import * as blueslip from "./blueslip";

const subs_by_stream_id = new Map();

export function get(stream_id) {
    return subs_by_stream_id.get(stream_id);
}

export function validate_stream_ids(stream_ids) {
    const good_ids = [];
    const bad_ids = [];

    for (const stream_id of stream_ids) {
        if (subs_by_stream_id.has(stream_id)) {
            good_ids.push(stream_id);
        } else {
            bad_ids.push(stream_id);
        }
    }

    if (bad_ids.length > 0) {
        blueslip.warn(`We have untracked stream_ids: ${bad_ids}`);
    }

    return good_ids;
}

export function clear() {
    subs_by_stream_id.clear();
}

export function delete_sub(stream_id) {
    subs_by_stream_id.delete(stream_id);
}

export function add_hydrated_sub(stream_id, sub) {
    // The only code that should call this directly is
    // in stream_data.js. Grep there to find callers.
    subs_by_stream_id.set(stream_id, sub);
}
