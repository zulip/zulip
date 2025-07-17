import assert from "minimalistic-assert";

import {$t} from "./i18n.ts";
import * as settings_config from "./settings_config.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

let first_render_completed = false;
let current_sections: StreamListSection[] = [];
let all_streams: number[] = [];

// Because we need to check whether we are filtering inactive streams
// in a loop over all streams to render the left sidebar, and the
// definition of demote_inactive_streams involves how many streams
// there are, we maintain this variable as a cache of the calculation
// to avoid making left sidebar rendering a quadratic operation.
let filter_out_inactives = false;

export function get_stream_ids(): number[] {
    return [...all_streams];
}

function current_section_ids_for_streams(): Map<number, StreamListSection> {
    const map = new Map<number, StreamListSection>();
    for (const section of current_sections) {
        for (const stream_id of [
            ...section.streams,
            ...section.muted_streams,
        ]) {
            map.set(stream_id, section);
        }
    }
    return map;
}

export function current_section_id_for_stream(stream_id: number): string {
    // Warning: This function is O(n), so it should not be called in a loop.
    const section = current_section_ids_for_streams().get(stream_id);
    assert(section !== undefined);
    return section.id;
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
    return sub.is_recently_active || sub.newly_subscribed;
}

export type StreamListSection = {
    id: string;
    section_title: string;
    streams: number[];
    muted_streams: number[]; // Not used for the inactive section
};

type StreamListSortResult = {
    same_as_before: boolean;
    sections: StreamListSection[];
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

    const pinned_section: StreamListSection = {
        id: "pinned-streams",
        section_title: $t({defaultMessage: "PINNED CHANNELS"}),
        streams: [],
        muted_streams: [],
    };
    const normal_section: StreamListSection = {
        id: "normal-streams",
        section_title: $t({defaultMessage: "ACTIVE CHANNELS"}),
        streams: [],
        muted_streams: [],
    };
    const dormant_section: StreamListSection = {
        id: "dormant-streams",
        section_title: $t({defaultMessage: "INACTIVE CHANNELS"}),
        streams: [],
        muted_streams: [], // Not used for the dormant section
    };

    for (const stream_id of stream_ids) {
        const sub = sub_store.get(stream_id);
        assert(sub);
        if (sub.is_archived) {
            continue;
        }
        if (sub.pin_to_top) {
            if (sub.is_muted) {
                pinned_section.muted_streams.push(stream_id);
            } else {
                pinned_section.streams.push(stream_id);
            }
        } else if (is_normal(sub)) {
            if (sub.is_muted) {
                normal_section.muted_streams.push(stream_id);
            } else {
                normal_section.streams.push(stream_id);
            }
        } else {
            dormant_section.streams.push(stream_id);
        }
    }

    // This needs to have the same ordering as the order they're displayed in the sidebar.
    const new_sections = [pinned_section, normal_section, dormant_section];

    for (const section of new_sections) {
        section.streams.sort(compare_function);
        section.muted_streams.sort(compare_function);
    }

    const same_as_before =
        first_render_completed &&
        new_sections.entries().every(([i, new_section]) => {
            const current_section = current_sections.at(i);
            return (
                current_section !== undefined &&
                new_section.id === current_section.id &&
                new_section.section_title === current_section.section_title &&
                util.array_compare(new_section.streams, current_section.streams) &&
                util.array_compare(new_section.muted_streams, current_section.muted_streams)
            );
        });

    if (!same_as_before) {
        first_render_completed = true;
        current_sections = new_sections;
        all_streams = new_sections.flatMap((section) => [
            ...section.streams,
            ...section.muted_streams,
        ]);
    }

    return {
        same_as_before,
        sections: new_sections,
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

    if (i === -1) {
        return undefined;
    }

    return maybe_get_stream_id(i - 1);
}

export function next_stream_id(stream_id: number): number | undefined {
    const i = all_streams.indexOf(stream_id);

    if (i === -1) {
        return undefined;
    }

    return maybe_get_stream_id(i + 1);
}

export function initialize(): void {
    set_filter_out_inactives();
}
