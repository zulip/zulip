import _ from "lodash";

import * as all_messages_data from "./all_messages_data.ts";
import type {Filter} from "./filter.ts";
import type {MessageListData} from "./message_list_data.ts";

// LRU cache for message list data.
//
// While it's unlikely that user will narrow to empty filter,
// but we will still need to update all_messages_data since it used
// as super set for populating other views.
let cache = new Map<number, MessageListData>([[0, all_messages_data.all_messages_data]]);
let latest_key = 0;

// Maximum number of data items to cache.
const CACHE_STORAGE_LIMIT = 100;

function move_to_end(key: number, cached_data: MessageListData): void {
    // Move the item to the end of the cache.
    // Map remembers the original insertion order of the keys.
    cache.delete(key);
    latest_key += 1;
    cache.set(latest_key, cached_data);

    // In theory, a cache like this might need to consider integer
    // overflow on latest_key, but that's not a realistic possibility
    // with how these data structures are used given the lifetime on a
    // Zulip web app window.
}

export function get(filter: Filter): MessageListData | undefined {
    for (const [key, cached_data] of cache.entries()) {
        if (cached_data.filter.equals(filter)) {
            move_to_end(key, cached_data);
            return cached_data;
        }
    }
    return undefined;
}

export function add(message_list_data: MessageListData): void {
    for (const [key, cached_data] of cache.entries()) {
        if (cached_data.filter.equals(message_list_data.filter)) {
            // We could chose to maintain in the cache the
            // message_list_data passed in, or the one already in the
            // cache. These can be different primarily when they
            // represent non-overlapping ID ranges.
            //
            // Saving the more current of the two message lists seems
            // like a better tiebreak, but we may be able to eliminate
            // this class of case if we implement the plan in #16697.
            move_to_end(key, message_list_data);
            return;
        }
    }

    if (cache.size >= CACHE_STORAGE_LIMIT) {
        // Remove the oldest item from the cache.
        for (const [key, cached_data] of cache.entries()) {
            // We never want to remove the all_messages_data from the cache.
            if (cached_data.filter.equals(all_messages_data.all_messages_data.filter)) {
                continue;
            }
            cache.delete(key);
            break;
        }
    }

    latest_key += 1;
    cache.set(latest_key, message_list_data);
}

export function all(): MessageListData[] {
    return [...cache.values()];
}

export function clear(): void {
    cache = new Map([[0, all_messages_data.all_messages_data]]);
    latest_key = 0;
}

function get_supersets_containing_near_or_with_msg(filter: Filter): MessageListData[] {
    const supersets_containing_near_or_with_msg = [];
    // For `near` / `with` operators, we can try populating from a dataset
    // that contains the message.
    let message_id: number | undefined;
    if (filter.has_operator("near")) {
        message_id = Number.parseInt(filter.terms_with_operator("near")[0]!.operand, 10);
    } else if (filter.has_operator("with")) {
        message_id = Number.parseInt(filter.terms_with_operator("with")[0]!.operand, 10);
    }
    if (message_id !== undefined) {
        for (const cached_data of cache.values()) {
            // Only consider superset datasets that contain contiguous message history.
            if (
                !cached_data.filter.single_term_type_returns_all_messages_of_conversation() ||
                !_.isEqual(cached_data.filter.sorted_term_types(), ["channel", "topic", "near"])
            ) {
                continue;
            }
            if (cached_data.get(message_id)) {
                supersets_containing_near_or_with_msg.push(cached_data);
            }
        }
    }
    return supersets_containing_near_or_with_msg;
}

export function get_superset_datasets(filter: Filter): MessageListData[] {
    let supersets_containing_near_or_with_msg: MessageListData[] = [];
    if (filter.is_conversation_view() || filter.is_conversation_view_with_near()) {
        supersets_containing_near_or_with_msg = get_supersets_containing_near_or_with_msg(filter);
    }

    let supersets = [];
    const exact_match = get(filter);
    // 1. Exact match has the highest priority.
    if (exact_match) {
        supersets.push(exact_match);
    }
    // 2. supersets_containing_near_or_with_msg.
    supersets = [...supersets, ...supersets_containing_near_or_with_msg];
    if (!supersets.includes(all_messages_data.all_messages_data)) {
        // 3. all_messages_data
        supersets.push(all_messages_data.all_messages_data);
    }

    return supersets;
}

export function remove(filter: Filter): void {
    for (const [key, cached_data] of cache.entries()) {
        if (cached_data.filter.equals(filter)) {
            cache.delete(key);
            return;
        }
    }
}
