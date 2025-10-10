import assert from "minimalistic-assert";
import type * as z from "zod/mini";

import {FoldDict} from "./fold_dict.ts";
import type {ChannelFolderUpdateEvent} from "./server_event_types.ts";
import type {StateData, channel_folder_schema} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as util from "./util.ts";

export type ChannelFolder = z.infer<typeof channel_folder_schema>;

let channel_folder_name_dict: FoldDict<ChannelFolder>;
let channel_folder_by_id_dict: Map<number, ChannelFolder>;
let active_channel_folder_ids: Set<number>;

export function clean_up_description(channel_folder: ChannelFolder): void {
    if (channel_folder.rendered_description !== undefined) {
        channel_folder.rendered_description = channel_folder.rendered_description
            .replace("<p>", "")
            .replace("</p>", "");
    }
}

export function add(channel_folder: ChannelFolder): void {
    clean_up_description(channel_folder);
    channel_folder_name_dict.set(channel_folder.name, channel_folder);
    channel_folder_by_id_dict.set(channel_folder.id, channel_folder);
    if (!channel_folder.is_archived) {
        active_channel_folder_ids.add(channel_folder.id);
    }
}

export function initialize(params: StateData["channel_folders"]): void {
    channel_folder_name_dict = new FoldDict();
    channel_folder_by_id_dict = new Map<number, ChannelFolder>();
    active_channel_folder_ids = new Set<number>();

    for (const channel_folder of params.channel_folders) {
        add(channel_folder);
    }
}

export function get_channel_folders(include_archived = false): ChannelFolder[] {
    const channel_folders = [...channel_folder_by_id_dict.values()];
    return channel_folders
        .filter((channel_folder) => {
            if (!include_archived && channel_folder.is_archived) {
                return false;
            }

            return true;
        })
        .toSorted((folder_a, folder_b) => folder_a.order - folder_b.order);
}

export function get_active_folder_ids(): Set<number> {
    return active_channel_folder_ids;
}

export function get_all_folder_ids(): Set<number> {
    return new Set(channel_folder_by_id_dict.keys());
}

export function is_valid_folder_id(folder_id: number): boolean {
    return channel_folder_by_id_dict.has(folder_id);
}

export function get_channel_folder_by_id(folder_id: number): ChannelFolder {
    const channel_folder = channel_folder_by_id_dict.get(folder_id);
    assert(channel_folder !== undefined);
    return channel_folder;
}

export function user_has_folders(): boolean {
    const subscribed_subs = stream_data.subscribed_subs();

    for (const sub of subscribed_subs) {
        if (sub.folder_id) {
            return true;
        }
    }

    return false;
}

export function update_channel_folder(
    folder_id: number,
    property: "name" | "description" | "rendered_description" | "is_archived",
    value: string | boolean,
): void {
    const channel_folder = get_channel_folder_by_id(folder_id);

    if (property === "is_archived") {
        assert(typeof value === "boolean");
        channel_folder.is_archived = value;
        if (channel_folder.is_archived) {
            active_channel_folder_ids.delete(channel_folder.id);
        }
        return;
    }

    assert(typeof value === "string");
    const old_value = channel_folder[property];

    channel_folder[property] = value;

    if (property === "name") {
        channel_folder_name_dict.delete(old_value);
        channel_folder_name_dict.set(channel_folder.name, channel_folder);
    }

    if (property === "rendered_description") {
        clean_up_description(channel_folder);
    }
}

export function update(event: ChannelFolderUpdateEvent): void {
    const folder_id = event.channel_folder_id;
    if (event.data.name !== undefined) {
        update_channel_folder(folder_id, "name", event.data.name);
    }

    if (event.data.description !== undefined) {
        update_channel_folder(folder_id, "description", event.data.description);
        assert(event.data.rendered_description !== undefined);
        update_channel_folder(folder_id, "rendered_description", event.data.rendered_description);
    }

    if (event.data.is_archived !== undefined) {
        update_channel_folder(folder_id, "is_archived", event.data.is_archived);
    }
}

export function get_stream_ids_in_folder(folder_id: number): number[] {
    const streams = stream_data.get_unsorted_subs().filter((sub) => sub.folder_id === folder_id);
    return streams.map((sub) => sub.stream_id);
}

export function get_channels_in_folders_matching_search_term_in_folder_name(
    search_term: string,
    all_subscribed_stream_ids: Set<number>,
): number[] {
    const channel_folders = get_channel_folders();
    const matching_channel_folders = util.filter_by_word_prefix_match(
        channel_folders,
        search_term,
        (channel_folder) => channel_folder.name,
    );

    const channel_ids: number[] = [];
    for (const channel_folder of matching_channel_folders) {
        for (const stream_id of get_stream_ids_in_folder(channel_folder.id)) {
            if (all_subscribed_stream_ids.has(stream_id)) {
                channel_ids.push(stream_id);
            }
        }
    }
    return channel_ids;
}

export function reorder(order: number[]): void {
    for (const [index, folder_id] of order.entries()) {
        const channel_folder = get_channel_folder_by_id(folder_id);
        channel_folder.order = index;
    }
}
