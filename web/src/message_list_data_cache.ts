import type {Filter} from "./filter.ts";
import type {MessageListData} from "./message_list_data.ts";
import * as recent_view_messages_data from "./recent_view_messages_data.ts";

// LRU cache for message list data.
//
// While it's unlikely that user will narrow to empty filter,
// but we will still need to update recent_view_messages_data since it used
// as super set for populating other views.
let cache = new Map<number, MessageListData>([
    [0, recent_view_messages_data.recent_view_messages_data],
]);
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
            // We never want to remove the recent_view_messages_data from the cache.
            if (
                cached_data.filter.equals(
                    recent_view_messages_data.recent_view_messages_data.filter,
                )
            ) {
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
    cache = new Map([[0, recent_view_messages_data.recent_view_messages_data]]);
    latest_key = 0;
}

function get_supersets_containing_anchor_msg(filter: Filter): MessageListData[] {
    // For a target conversation view anchored at a `near`/`with` message,
    // look for other cached conversation views (with or without their own
    // `near`/`with`) that already hold that message. Restricting candidates
    // to conversation views via `is_conversation_view` ensures a candidate
    // cannot have silently dropped a message the target needs:
    //
    //  - `excludes_muted_topics` is false for every conversation-view shape,
    //    so muted-topic filtering never drops a candidate message.
    //  - `excludes_muted_users` is true for channel+topic shapes (and false
    //    for DM shapes), but channel and DM messages never share a dataset,
    //    and the flag is identical across views of the same shape. So
    //    whenever a candidate can actually supply the target's messages, it
    //    has dropped only the messages the target would drop too.
    let message_id: number | undefined;
    if (filter.has_operator("with")) {
        message_id = Number.parseInt(filter.terms_with_operator("with")[0]!.operand, 10);
    } else if (filter.has_operator("near")) {
        message_id = Number.parseInt(filter.terms_with_operator("near")[0]!.operand, 10);
    }
    if (message_id === undefined || Number.isNaN(message_id)) {
        return [];
    }

    // Iterate most-recently-used first so the freshest cached dataset wins
    // when several contain the anchor.
    const supersets: MessageListData[] = [];
    for (const cached_data of [...cache.values()].toReversed()) {
        if (!cached_data.filter.is_conversation_view()) {
            continue;
        }
        if (cached_data.get(message_id) !== undefined) {
            supersets.push(cached_data);
        }
    }
    return supersets;
}

export function get_superset_datasets(filter: Filter): MessageListData[] {
    // The returned datasets are tried in order by the caller; the first one
    // that contains the messages needed to locally render the target narrow
    // wins. Earlier entries are higher-priority (more specific) candidates.
    const supersets: MessageListData[] = [];
    const recent = recent_view_messages_data.recent_view_messages_data;

    const exact_match = get(filter);
    if (exact_match !== undefined) {
        supersets.push(exact_match);
    }

    if (filter.is_conversation_view()) {
        for (const cached_data of get_supersets_containing_anchor_msg(filter)) {
            if (!supersets.includes(cached_data)) {
                supersets.push(cached_data);
            }
        }
    }

    if (!supersets.includes(recent)) {
        supersets.push(recent);
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
