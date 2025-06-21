import assert from "minimalistic-assert";

import * as channel_folders from "./channel_folders.ts";
import {$t} from "./i18n.ts";
import * as settings_config from "./settings_config.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

let first_render_completed = false;
let previous_sections: StreamListSection[] = [];
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
        section_title: $t({defaultMessage: "OTHER CHANNELS"}),
        streams: [],
        muted_streams: [],
    };
    const dormant_section: StreamListSection = {
        id: "dormant-streams",
        section_title: $t({defaultMessage: "INACTIVE CHANNELS"}),
        streams: [],
        muted_streams: [], // Not used for the dormant section
    };

    const folder_sections = new Map<number, StreamListSection>();

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
        } else if (sub.folder_id) {
            const folder = channel_folders.get_channel_folder_by_id(sub.folder_id);
            let section = folder_sections.get(sub.folder_id);
            if (!section) {
                section = {
                    id: sub.folder_id.toString(),
                    section_title: folder.name.toUpperCase(),
                    streams: [],
                    muted_streams: [],
                };
                folder_sections.set(sub.folder_id, section);
            }
            if (sub.is_muted) {
                section.muted_streams.push(stream_id);
            } else {
                section.streams.push(stream_id);
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

    const folder_sections_sorted = [...folder_sections.values()].sort((section_a, section_b) =>
        util.strcmp(section_a.section_title, section_b.section_title),
    );

    // This needs to have the same ordering as the order they're displayed in the sidebar.
    const sections = [pinned_section, ...folder_sections_sorted, normal_section, dormant_section];

    // Don't call it "other channels" if there's nothing above it.
    if (
        folder_sections_sorted.length === 0 &&
        pinned_section.streams.length === 0 &&
        pinned_section.muted_streams.length === 0
    ) {
        normal_section.section_title = $t({defaultMessage: "CHANNELS"});
    }

    for (const section of sections) {
        section.streams.sort(compare_function);
        section.muted_streams.sort(compare_function);
    }

    const same_as_before =
        first_render_completed &&
        sections.entries().every((entry) => {
            const i = entry[0];
            const section = entry[1];
            const previous_section = previous_sections.at(i);
            return (
                previous_section !== undefined &&
                section.id === previous_section.id &&
                section.section_title === previous_section.section_title &&
                util.array_compare(section.streams, previous_section.streams) &&
                util.array_compare(section.muted_streams, previous_section.muted_streams)
            );
        });

    if (!same_as_before) {
        first_render_completed = true;
        previous_sections = sections;
        all_streams = sections.flatMap((section) => [...section.streams, ...section.muted_streams]);
    }

    return {
        same_as_before,
        sections,
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
