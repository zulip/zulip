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

export function get_superset_datasets(filter: Filter): MessageListData[] {
    const superset_datasets = [];
    // Try to get exact match first.
    const superset_data = get(filter);
    if (superset_data !== undefined) {
        // TODO: Search for additional superset datasets.
        superset_datasets.push(superset_data);
    }

    return [...superset_datasets, all_messages_data.all_messages_data];
}

export function remove(filter: Filter): void {
    for (const [key, cached_data] of cache.entries()) {
        if (cached_data.filter.equals(filter)) {
            cache.delete(key);
            return;
        }
    }
}
