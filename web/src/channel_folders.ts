import assert from "minimalistic-assert";
import type * as z from "zod/mini";

import {FoldDict} from "./fold_dict.ts";
import type {ChannelFolderUpdateEvent} from "./server_event_types.ts";
import type {StateData, channel_folder_schema} from "./state_data.ts";

export type ChannelFolder = z.infer<typeof channel_folder_schema>;

let channel_folder_name_dict: FoldDict<ChannelFolder>;
let channel_folder_by_id_dict: Map<number, ChannelFolder>;

export const MAX_CHANNEL_FOLDER_NAME_LENGTH = 100;
export const MAX_CHANNEL_FOLDER_DESCRIPTION_LENGTH = 1024;

export function add(channel_folder: ChannelFolder): void {
    channel_folder_name_dict.set(channel_folder.name, channel_folder);
    channel_folder_by_id_dict.set(channel_folder.id, channel_folder);
}

export function initialize(params: StateData["channel_folders"]): void {
    channel_folder_name_dict = new FoldDict();
    channel_folder_by_id_dict = new Map<number, ChannelFolder>();

    for (const channel_folder of params.channel_folders) {
        add(channel_folder);
    }
}

export function get_channel_folders(include_archived = false): ChannelFolder[] {
    const channel_folders = [...channel_folder_by_id_dict.values()].sort((a, b) => a.id - b.id);
    return channel_folders.filter((channel_folder) => {
        if (!include_archived && channel_folder.is_archived) {
            return false;
        }

        return true;
    });
}

/* TODO/channel-folders: Remove when tests are restored */
/* istanbul ignore next */
export function get_all_folder_ids(): number[] {
    return [...channel_folder_by_id_dict.keys()];
}

export function is_valid_folder_id(folder_id: number): boolean {
    return channel_folder_by_id_dict.has(folder_id);
}

export function get_channel_folder_by_id(folder_id: number): ChannelFolder {
    const channel_folder = channel_folder_by_id_dict.get(folder_id);
    assert(channel_folder !== undefined);
    return channel_folder;
}

export function update(event: ChannelFolderUpdateEvent): void {
    const folder_id = event.channel_folder_id;
    const channel_folder = get_channel_folder_by_id(folder_id);
    if (event.data.name !== undefined) {
        channel_folder_name_dict.delete(channel_folder.name);
        channel_folder.name = event.data.name;
        channel_folder_name_dict.set(channel_folder.name, channel_folder);
    }

    if (event.data.description !== undefined) {
        channel_folder.description = event.data.description;
        assert(event.data.rendered_description !== undefined);
        channel_folder.rendered_description = event.data.rendered_description;
    }

    if (event.data.is_archived !== undefined) {
        channel_folder.is_archived = event.data.is_archived;
        channel_folder_name_dict.delete(channel_folder.name);
        channel_folder_name_dict.set(channel_folder.name, channel_folder);
    }
}
