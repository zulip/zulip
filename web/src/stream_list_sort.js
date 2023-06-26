import * as settings_config from "./settings_config";
import * as stream_data from "./stream_data";
import * as stream_topic_history from "./stream_topic_history";
import * as sub_store from "./sub_store";
import {user_settings} from "./user_settings";
import * as util from "./util";

let previous_pinned;
let previous_normal;
let previous_dormant;
let previous_muted_active;
let previous_muted_pinned;
let all_streams = [];

// Because we need to check whether we are filtering inactive streams
// in a loop over all streams to render the left sidebar, and the
// definition of demote_inactive_streams involves how many streams
// there are, we maintain this variable as a cache of the calculation
// to avoid making left sidebar rendering a quadratic operation.
let filter_out_inactives = false;

export function get_streams() {
    const sorted_streams = all_streams.map((stream_id) =>
        sub_store.maybe_get_stream_name(stream_id),
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

export function set_filter_out_inactives() {
    if (
        user_settings.demote_inactive_streams ===
        settings_config.demote_inactive_streams_values.automatic.code
    ) {
        filter_out_inactives = stream_data.num_subscribed_subs() >= 30;
    } else if (
        user_settings.demote_inactive_streams ===
        settings_config.demote_inactive_streams_values.always.code
    ) {
        filter_out_inactives = true;
    } else {
        filter_out_inactives = false;
    }
}

// Exported for access by unit tests.
export function is_filtering_inactives() {
    return filter_out_inactives;
}

export function has_recent_activity(sub) {
    if (!filter_out_inactives || sub.pin_to_top) {
        // If users don't want to filter inactive streams
        // to the bottom, we respect that setting and don't
        // treat any streams as dormant.
        //
        // Currently this setting is automatically determined
        // by the number of streams.  See the callers
        // to set_filter_out_inactives.
        return true;
    }
    return stream_topic_history.stream_has_topics(sub.stream_id) || sub.newly_subscribed;
}

export function has_recent_activity_but_muted(sub) {
    return has_recent_activity(sub) && sub.is_muted;
}

export function sort_groups(streams, search_term) {
    const stream_id_to_name = (stream) => sub_store.get(stream).name;
    // Use -, _ and / as word separators apart from the default space character
    const word_separator_regex = /[\s/_-]/;
    streams = util.filter_by_word_prefix_match(
        streams,
        search_term,
        stream_id_to_name,
        word_separator_regex,
    );

    function is_normal(sub) {
        return has_recent_activity(sub);
    }

    const pinned_streams = [];
    const normal_streams = [];
    const muted_pinned_streams = [];
    const muted_active_streams = [];
    const dormant_streams = [];

    for (const stream of streams) {
        const sub = sub_store.get(stream);
        const pinned = sub.pin_to_top;
        if (pinned) {
            if (!sub.is_muted) {
                pinned_streams.push(stream);
            } else {
                muted_pinned_streams.push(stream);
            }
        } else if (is_normal(sub)) {
            if (!sub.is_muted) {
                normal_streams.push(stream);
            } else {
                muted_active_streams.push(stream);
            }
        } else {
            dormant_streams.push(stream);
        }
    }

    pinned_streams.sort(compare_function);
    normal_streams.sort(compare_function);
    muted_pinned_streams.sort(compare_function);
    muted_active_streams.sort(compare_function);
    dormant_streams.sort(compare_function);

    const same_as_before =
        previous_pinned !== undefined &&
        util.array_compare(previous_pinned, pinned_streams) &&
        util.array_compare(previous_normal, normal_streams) &&
        util.array_compare(previous_muted_pinned, muted_pinned_streams) &&
        util.array_compare(previous_muted_active, muted_active_streams) &&
        util.array_compare(previous_dormant, dormant_streams);

    if (!same_as_before) {
        previous_pinned = pinned_streams;
        previous_normal = normal_streams;
        previous_muted_pinned = muted_pinned_streams;
        previous_muted_active = muted_active_streams;
        previous_dormant = dormant_streams;

        all_streams = [
            ...pinned_streams,
            ...muted_pinned_streams,
            ...normal_streams,
            ...muted_active_streams,
            ...dormant_streams,
        ];
    }

    return {
        same_as_before,
        pinned_streams,
        normal_streams,
        dormant_streams,
        muted_pinned_streams,
        muted_active_streams,
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

export function initialize() {
    set_filter_out_inactives();
}
