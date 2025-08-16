import assert from "minimalistic-assert";

import * as channel_folders from "./channel_folders.ts";
import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";
import * as settings_config from "./settings_config.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as topic_list_data from "./topic_list_data.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

let first_render_completed = false;
let current_sections: StreamListSection[] = [];

export type StreamListRow =
    | {
          type: "stream";
          stream_id: number;
          inactive_or_muted: boolean;
      }
    | {
          type: "inactive_or_muted_toggle";
          section_id: string;
      };
let all_rows: StreamListRow[] = [];

// Because we need to check whether we are filtering inactive streams
// in a loop over all streams to render the left sidebar, and the
// definition of demote_inactive_streams involves how many streams
// there are, we maintain this variable as a cache of the calculation
// to avoid making left sidebar rendering a quadratic operation.
let filter_out_inactives = false;

export function get_all_rows_for_testing(): StreamListRow[] {
    return all_rows;
}

export function reset_stream_list_for_testing(): void {
    all_rows = [];
    first_render_completed = false;
}

export function set_filter_out_inactives_for_testing(value: boolean): void {
    filter_out_inactives = value;
}

export function get_stream_ids(): number[] {
    return all_rows.flatMap((row) => (row.type === "stream" ? row.stream_id : []));
}

export function section_ids(): string[] {
    return current_sections.map((section) => section.id);
}

function current_section_ids_for_streams(): Map<number, StreamListSection> {
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

// Will return undefined if the given stream isn't in the user's stream
// list (i.e. they're not subscribed to it).
export function current_section_id_for_stream(stream_id: number): string | undefined {
    // Warning: This function is O(n), so it should not be called in a loop.
    return current_section_ids_for_streams().get(stream_id)?.id;
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
        filter_out_inactives = stream_data.num_subscribed_subs() >= 20;
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
    folder_id: number | null;
    section_title: string;
    streams: number[];
    muted_streams: number[];
    inactive_streams: number[];
    order?: number; // Only used for folder sections
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

    const current_channel_id = narrow_state.stream_id(narrow_state.filter(), true);
    if (
        current_channel_id !== undefined &&
        stream_data.is_subscribed(current_channel_id) &&
        !stream_ids.includes(current_channel_id) &&
        // If any of the topics of the channel match the search term, we need to
        // include the channel in the list of streams.
        topic_list_data.get_list_info(current_channel_id, false, (topic_names) =>
            topic_list_data.filter_topics_by_search_term(topic_names, search_term),
        ).items.length > 0
    ) {
        stream_ids.push(current_channel_id);
    }

    const pinned_section: StreamListSection = {
        id: "pinned-streams",
        folder_id: null,
        section_title: $t({defaultMessage: "PINNED CHANNELS"}),
        streams: [],
        muted_streams: [],
        inactive_streams: [],
    };
    const normal_section: StreamListSection = {
        id: "normal-streams",
        folder_id: null,
        section_title: $t({defaultMessage: "CHANNELS"}),
        streams: [],
        muted_streams: [],
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
                // Inactive channels aren't treated differently when pinned,
                // since the user wants chose to put them in the pinned section.
                pinned_section.streams.push(stream_id);
            }
        } else if (user_settings.web_left_sidebar_show_channel_folders && sub.folder_id) {
            const folder = channel_folders.get_channel_folder_by_id(sub.folder_id);
            let section = folder_sections.get(sub.folder_id);
            if (!section) {
                section = {
                    id: sub.folder_id.toString(),
                    folder_id: sub.folder_id,
                    section_title: folder.name.toUpperCase(),
                    streams: [],
                    muted_streams: [],
                    inactive_streams: [],
                    order: folder.order,
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
        } else {
            if (!has_recent_activity(sub)) {
                normal_section.inactive_streams.push(stream_id);
            } else if (sub.is_muted) {
                normal_section.muted_streams.push(stream_id);
            } else {
                normal_section.streams.push(stream_id);
            }
        }
    }

    const folder_sections_sorted = [...folder_sections.values()].sort(
        (section_a, section_b) => section_a.order! - section_b.order!,
    );

    // This needs to have the same ordering as the order they're displayed in the sidebar.
    const new_sections = [pinned_section, ...folder_sections_sorted, normal_section];

    for (const section of new_sections) {
        section.streams.sort(compare_function);
        section.muted_streams.sort(compare_function);
        section.inactive_streams.sort(compare_function);
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
                util.array_compare(new_section.muted_streams, current_section.muted_streams) &&
                util.array_compare(new_section.inactive_streams, current_section.inactive_streams)
            );
        });

    if (!same_as_before) {
        first_render_completed = true;
        current_sections = new_sections;
        all_rows = [];
        for (const section of current_sections) {
            for (const stream_id of section.streams) {
                all_rows.push({
                    type: "stream",
                    stream_id,
                    inactive_or_muted: false,
                });
            }
            for (const stream_id of [...section.muted_streams, ...section.inactive_streams]) {
                all_rows.push({
                    type: "stream",
                    stream_id,
                    inactive_or_muted: true,
                });
            }
            if (section.inactive_streams.length > 0 || section.muted_streams.length > 0) {
                all_rows.push({
                    type: "inactive_or_muted_toggle",
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

function is_visible_row(
    row: StreamListRow,
    section_id_map: Map<number, StreamListSection>,
    sections_showing_inactive_or_muted: Set<string>,
    collapsed_sections: Set<string>,
    active_stream_id: number | undefined,
): boolean {
    if (row.type === "stream") {
        const stream_id = row.stream_id;
        assert(stream_id !== undefined);
        const section = section_id_map.get(stream_id)!;
        if (collapsed_sections.has(section.id) && active_stream_id !== stream_id) {
            return false;
        }
        if (!sections_showing_inactive_or_muted.has(section.id) && row.inactive_or_muted) {
            return false;
        }
    } else if (row.type === "inactive_or_muted_toggle" && collapsed_sections.has(row.section_id)) {
        return false;
    }
    return true;
}

export function prev_row(
    row: StreamListRow,
    sections_showing_inactive_or_muted: Set<string>,
    collapsed_sections: Set<string>,
    active_stream_id: number | undefined,
): StreamListRow | undefined {
    let i = all_rows.indexOf(row);
    const section_id_map = current_section_ids_for_streams();
    while (i > 0) {
        i -= 1;
        const prev_row = all_rows[i]!;
        if (
            is_visible_row(
                prev_row,
                section_id_map,
                sections_showing_inactive_or_muted,
                collapsed_sections,
                active_stream_id,
            )
        ) {
            return prev_row;
        }
    }
    return undefined;
}

export function next_row(
    row: StreamListRow,
    sections_showing_inactive_or_muted: Set<string>,
    collapsed_sections: Set<string>,
    active_stream_id: number | undefined,
): StreamListRow | undefined {
    let i = all_rows.indexOf(row);
    const section_id_map = current_section_ids_for_streams();
    while (i + 1 < all_rows.length) {
        i += 1;
        const next_row = all_rows[i]!;
        if (
            is_visible_row(
                next_row,
                section_id_map,
                sections_showing_inactive_or_muted,
                collapsed_sections,
                active_stream_id,
            )
        ) {
            return next_row;
        }
    }
    return undefined;
}

export function initialize(): void {
    set_filter_out_inactives();
}
