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
let current_sections: StreamListSection[] = [];

export type StreamListRow =
    | {
          type: "stream";
          stream_id: number;
          inactive: boolean;
      }
    | {
          type: "inactive_toggle";
          section_id: string;
      };
let all_rows: StreamListRow[] = [];

// Because we need to check whether we are filtering inactive streams
// in a loop over all streams to render the left sidebar, and the
// definition of demote_inactive_streams involves how many streams
// there are, we maintain this variable as a cache of the calculation
// to avoid making left sidebar rendering a quadratic operation.
let filter_out_inactives = false;

export function get_stream_ids(): number[] {
    return all_rows.flatMap((row) => (row.type === "stream" ? row.stream_id : []));
}

function stream_id_to_section_id(): Map<number, StreamListSection> {
    const map = new Map<number, StreamListSection>();
    for (const section of current_sections) {
        for (const stream_id of [
            ...section.streams,
            ...section.muted_streams,
            ...section.inactive_streams,
        ]) {
            map.set(stream_id, section);
        }
    }
    return map;
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
    inactive_streams: number[]; // Only used for folder sections
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
        inactive_streams: [],
    };
    const normal_section: StreamListSection = {
        id: "normal-streams",
        section_title: $t({defaultMessage: "OTHER CHANNELS"}),
        streams: [],
        muted_streams: [],
        inactive_streams: [],
    };
    const dormant_section: StreamListSection = {
        id: "dormant-streams",
        section_title: $t({defaultMessage: "INACTIVE CHANNELS"}),
        streams: [],
        muted_streams: [], // Not used for the dormant section
        inactive_streams: [],
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
                    inactive_streams: [],
                };
                folder_sections.set(sub.folder_id, section);
            }
            if (!has_recent_activity(sub)) {
                section.inactive_streams.push(stream_id);
            } else if (sub.is_muted) {
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
    const new_sections = [pinned_section, ...folder_sections_sorted, normal_section, dormant_section];

    // Don't call it "other channels" if there's nothing above it.
    if (
        folder_sections_sorted.length === 0 &&
        pinned_section.streams.length === 0 &&
        pinned_section.muted_streams.length === 0
    ) {
        normal_section.section_title = $t({defaultMessage: "CHANNELS"});
    }

    for (const section of new_sections) {
        section.streams.sort(compare_function);
        section.muted_streams.sort(compare_function);
        section.inactive_streams.sort(compare_function);
    }

    const same_as_before =
        first_render_completed &&
        new_sections.entries().every((entry) => {
            const i = entry[0];
            const section = entry[1];
            const previous_section = current_sections.at(i);
            return (
                previous_section !== undefined &&
                section.id === previous_section.id &&
                section.section_title === previous_section.section_title &&
                util.array_compare(section.streams, previous_section.streams) &&
                util.array_compare(section.muted_streams, previous_section.muted_streams) &&
                util.array_compare(section.inactive_streams, previous_section.inactive_streams)
            );
        });

    if (!same_as_before) {
        first_render_completed = true;
        current_sections = new_sections;
        all_rows = [];
        for (const section of current_sections) {
            for (const stream_id of [...section.streams, ...section.muted_streams]) {
                all_rows.push({
                    type: "stream",
                    stream_id,
                    inactive: false,
                });
            }
            for (const stream_id of section.inactive_streams) {
                all_rows.push({
                    type: "stream",
                    stream_id,
                    inactive: true,
                });
            }
            if (section.inactive_streams.length > 0) {
                all_rows.push({
                    type: "inactive_toggle",
                    section_id: section.id,
                });
            }
        }
    }

    return {
        same_as_before,
        sections: new_sections,
    };
}

export function first_row(): StreamListRow | undefined {
    return all_rows.at(0);
}

export function prev_row(
    row: StreamListRow,
    sections_showing_inactive: Set<string>,
    collapsed_sections: Set<string>,
): StreamListRow | undefined {
    let i = all_rows.indexOf(row);
    const section_id_map = stream_id_to_section_id();
    while (i > 0) {
        i -= 1;
        const prev_row = all_rows[i]!;
        if (prev_row.type === "stream") {
            const stream_id = prev_row.stream_id;
            assert(stream_id !== undefined);
            const section = section_id_map.get(stream_id)!;
            if (collapsed_sections.has(section.id)) {
                continue;
            }
            if (!sections_showing_inactive.has(section.id) && prev_row.inactive) {
                continue;
            }
        } else if (
            prev_row.type === "inactive_toggle" &&
            collapsed_sections.has(prev_row.section_id)
        ) {
            continue;
        }
        return prev_row;
    }
    return undefined;
}

export function next_row_id(
    row: StreamListRow,
    sections_showing_inactive: Set<string>,
    collapsed_sections: Set<string>,
): StreamListRow | undefined {
    let i = all_rows.indexOf(row);
    const section_id_map = stream_id_to_section_id();
    while (i + 1 < all_rows.length) {
        i += 1;
        const next_row = all_rows[i]!;
        if (next_row.type === "stream") {
            const stream_id = next_row.stream_id;
            assert(stream_id !== undefined);
            const section = section_id_map.get(stream_id)!;
            if (collapsed_sections.has(section.id)) {
                continue;
            }
            if (!sections_showing_inactive.has(section.id) && next_row.inactive) {
                continue;
            }
        } else if (
            next_row.type === "inactive_toggle" &&
            collapsed_sections.has(next_row.section_id)
        ) {
            continue;
        }
        return next_row;
    }
    return undefined;
}

export function initialize(): void {
    set_filter_out_inactives();
}
