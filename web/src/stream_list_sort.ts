import assert from "minimalistic-assert";

import * as settings_config from "./settings_config";
import * as stream_data from "./stream_data";
import * as stream_topic_history from "./stream_topic_history";
import * as sub_store from "./sub_store";
import type {StreamSubscription} from "./sub_store";
import {user_settings} from "./user_settings";
import * as util from "./util";

let first_render_completed = false;
let previous_pinned: number[] = [];
let previous_normal: number[] = [];
let previous_dormant: number[] = [];
let previous_muted_active: number[] = [];
let previous_muted_pinned: number[] = [];
let all_streams: number[] = [];

// Because we need to check whether we are filtering inactive streams
// in a loop over all streams to render the left sidebar, and the
// definition of demote_inactive_streams involves how many streams
// there are, we maintain this variable as a cache of the calculation
// to avoid making left sidebar rendering a quadratic operation.
let filter_out_inactives = false;

export function get_streams(): string[] {
    return all_streams.flatMap((stream_id) => {
        const stream_name = sub_store.maybe_get_stream_name(stream_id);
        return stream_name === undefined ? [] : [stream_name];
    });
}

function compare_function(a: number, b: number): number {
    const stream_a = sub_store.get(a);
    const stream_b = sub_store.get(b);

    const stream_name_a = stream_a ? stream_a.name : "";
    const stream_name_b = stream_b ? stream_b.name : "";

    return util.strcmp(stream_name_a, stream_name_b);
}

export function set_filter_out_inactives(): void {
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
export function is_filtering_inactives(): boolean {
    return filter_out_inactives;
}

export function has_recent_activity(sub: StreamSubscription): boolean {
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

export function has_recent_activity_but_muted(sub: StreamSubscription): boolean {
    return has_recent_activity(sub) && sub.is_muted;
}

type StreamListSortResult = {
    same_as_before: boolean;
    pinned_streams: number[];
    normal_streams: number[];
    dormant_streams: number[];
    muted_pinned_streams: number[];
    muted_active_streams: number[];
};

export function sort_groups(stream_ids: number[], search_term: string): StreamListSortResult {
    const stream_id_to_name = (stream_id: number): string => sub_store.get(stream_id)!.name;
    // Use -, _, : and / as word separators apart from the default space character
    const word_separator_regex = /[\s/:_-]/;
    stream_ids = util.filter_by_word_prefix_match(
        stream_ids,
        search_term,
        stream_id_to_name,
        word_separator_regex,
    );

    function is_normal(sub: StreamSubscription): boolean {
        return has_recent_activity(sub);
    }

    const pinned_streams = [];
    const normal_streams = [];
    const muted_pinned_streams = [];
    const muted_active_streams = [];
    const dormant_streams = [];

    for (const stream_id of stream_ids) {
        const sub = sub_store.get(stream_id);
        assert(sub);
        const pinned = sub.pin_to_top;
        if (pinned) {
            if (!sub.is_muted) {
                pinned_streams.push(stream_id);
            } else {
                muted_pinned_streams.push(stream_id);
            }
        } else if (is_normal(sub)) {
            if (!sub.is_muted) {
                normal_streams.push(stream_id);
            } else {
                muted_active_streams.push(stream_id);
            }
        } else {
            dormant_streams.push(stream_id);
        }
    }

    pinned_streams.sort(compare_function);
    normal_streams.sort(compare_function);
    muted_pinned_streams.sort(compare_function);
    muted_active_streams.sort(compare_function);
    dormant_streams.sort(compare_function);

    const same_as_before =
        first_render_completed &&
        util.array_compare(previous_pinned, pinned_streams) &&
        util.array_compare(previous_normal, normal_streams) &&
        util.array_compare(previous_muted_pinned, muted_pinned_streams) &&
        util.array_compare(previous_muted_active, muted_active_streams) &&
        util.array_compare(previous_dormant, dormant_streams);

    if (!same_as_before) {
        first_render_completed = true;
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

function maybe_get_stream_id(i: number): number | undefined {
    if (i < 0 || i >= all_streams.length) {
        return undefined;
    }

    return all_streams[i];
}

export function first_stream_id(): number | undefined {
    return maybe_get_stream_id(0);
}

export function prev_stream_id(stream_id: number): number | undefined {
    const i = all_streams.indexOf(stream_id);

    if (i < 0) {
        return undefined;
    }

    return maybe_get_stream_id(i - 1);
}

export function next_stream_id(stream_id: number): number | undefined {
    const i = all_streams.indexOf(stream_id);

    if (i < 0) {
        return undefined;
    }

    return maybe_get_stream_id(i + 1);
}

export function initialize(): void {
    set_filter_out_inactives();
}
