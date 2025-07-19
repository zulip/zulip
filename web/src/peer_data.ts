import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import {LazySet} from "./lazy_set.ts";
import {page_params} from "./page_params.ts";
import type {User} from "./people.ts";
import * as people from "./people.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as sub_store from "./sub_store.ts";
import * as util from "./util.ts";

// This maps a stream_id to a LazySet of user_ids who are subscribed.
// Make sure that when we have full subscriber data for a stream,
// the size of its subscribers set stays synced with the relevant
// stream's `subscriber_count`.
const stream_subscribers = new Map<number, LazySet>();
const fetched_stream_ids = new Set<number>();
export function has_full_subscriber_data(stream_id: number): boolean {
    return fetched_stream_ids.has(stream_id);
}
const pending_subscriber_requests = new Map<
    number,
    {
        subscribers_promise: Promise<LazySet | null>;
        pending_peer_events: {
            type: "peer_add" | "peer_remove";
            user_ids: number[];
        }[];
    }
>();

export function clear_for_testing(): void {
    stream_subscribers.clear();
    fetched_stream_ids.clear();
    pending_subscriber_requests.clear();
}

const fetch_stream_subscribers_response_schema = z.object({
    subscribers: z.array(z.number()),
});

// This function will always resolve to a LazySet but could hang
// indefinitely trying to fetch data. `num_attempts` should only
// be set in the recursive call.
export async function maybe_fetch_stream_subscribers_with_retry(
    stream_id: number,
    num_attempts = 1,
): Promise<LazySet> {
    const subscribers = await maybe_fetch_stream_subscribers(stream_id);
    if (subscribers === null) {
        num_attempts += 1;
        const retry_delay_secs = util.get_retry_backoff_seconds(undefined, num_attempts);
        await new Promise((resolve) => setTimeout(resolve, retry_delay_secs));
        return maybe_fetch_stream_subscribers_with_retry(stream_id, num_attempts);
    }
    return subscribers;
}

export async function maybe_fetch_stream_subscribers(stream_id: number): Promise<LazySet | null> {
    if (pending_subscriber_requests.has(stream_id)) {
        return pending_subscriber_requests.get(stream_id)!.subscribers_promise;
    }
    const subscribers_promise = (async () => {
        let subscribers: number[];
        try {
            const result = await channel.get({
                url: `/json/streams/${stream_id}/members`,
            });
            subscribers = fetch_stream_subscribers_response_schema.parse(result).subscribers;
        } catch {
            blueslip.error("Failure fetching channel subscribers", {
                stream_id,
            });
            pending_subscriber_requests.delete(stream_id);
            return null;
        }

        set_subscribers(stream_id, subscribers);
        const pending_peer_events = pending_subscriber_requests.get(stream_id)!.pending_peer_events;
        pending_subscriber_requests.delete(stream_id);
        for (const event of pending_peer_events) {
            if (event.type === "peer_add") {
                bulk_add_subscribers({stream_ids: [stream_id], user_ids: event.user_ids});
            } else {
                bulk_remove_subscribers({stream_ids: [stream_id], user_ids: event.user_ids});
            }
        }
        return get_loaded_subscriber_subset(stream_id);
    })();

    pending_subscriber_requests.set(stream_id, {
        subscribers_promise,
        pending_peer_events: [],
    });
    return subscribers_promise;
}

function get_loaded_subscriber_subset(stream_id: number): LazySet {
    // This is an internal function to get the LazySet of users.
    // We create one on the fly as necessary, but we warn in that case.
    if (!sub_store.get(stream_id)) {
        blueslip.warn(
            `We called get_loaded_subscriber_subset for an untracked stream: ${stream_id}`,
        );
    }

    let subscribers = stream_subscribers.get(stream_id);

    if (subscribers === undefined) {
        subscribers = new LazySet([]);
        stream_subscribers.set(stream_id, subscribers);
    }

    return subscribers;
}

async function get_full_subscriber_set(stream_id: number, retry_on_failure: true): Promise<LazySet>;
async function get_full_subscriber_set(
    stream_id: number,
    retry_on_failure: boolean,
): Promise<LazySet | null>;
async function get_full_subscriber_set(
    stream_id: number,
    retry_on_failure: boolean,
): Promise<LazySet | null> {
    assert(!page_params.is_spectator);
    // This function parallels `get_loaded_subscriber_subset` but ensures we include all
    // subscribers, possibly fetching that data from the server.
    if (!fetched_stream_ids.has(stream_id) && sub_store.get(stream_id)) {
        let fetched_subscribers: LazySet | null;
        if (retry_on_failure) {
            fetched_subscribers = await maybe_fetch_stream_subscribers_with_retry(stream_id);
        } else {
            fetched_subscribers = await maybe_fetch_stream_subscribers(stream_id);
        }
        // This means a request failed and we don't know who the subscribers are.
        if (fetched_subscribers === null) {
            return null;
        }
        set_subscribers(stream_id, [...fetched_subscribers.keys()]);
    }
    return get_loaded_subscriber_subset(stream_id);
}

export async function is_subscriber_subset(
    stream_id1: number,
    stream_id2: number,
): Promise<boolean | null> {
    const sub1_promise = get_full_subscriber_set(stream_id1, false);
    const sub2_promise = get_full_subscriber_set(stream_id2, false);
    const sub1_set = await sub1_promise;
    const sub2_set = await sub2_promise;
    // This happens if we encountered an error feteching subscribers.
    if (sub1_set === null || sub2_set === null) {
        return null;
    }

    return [...sub1_set.keys()].every((key) => sub2_set.has(key));
}

export function potential_subscribers(stream_id: number): User[] {
    /*
        This is a list of unsubscribed users
        for the current stream, who the current
        user could potentially subscribe to the
        stream.  This may include some bots.

        We currently use it for typeahead in
        stream_edit.ts.

        This may be a superset of the actual
        subscribers that you can change in some cases
        (like if you're a guest?); we should refine this
        going forward, especially if we use it for something
        other than typeahead.  (The guest use case
        may be moot now for other reasons.)
    */
    if (!fetched_stream_ids.has(stream_id)) {
        blueslip.error("Fetching potential subscribers for stream without full subscriber data", {
            stream_id,
        });
    }
    const subscribers = get_loaded_subscriber_subset(stream_id);

    function is_potential_subscriber(person: User): boolean {
        // Use verbose style to force better test
        // coverage, plus we may add more conditions over
        // time.
        if (subscribers.has(person.user_id)) {
            return false;
        }

        return true;
    }

    return people.filter_all_users(is_potential_subscriber);
}

function increment_subscriber_count(sub: StreamSubscription, user_id: number): void {
    const subscribers = get_loaded_subscriber_subset(sub.stream_id);
    if (subscribers.has(user_id)) {
        return;
    }
    sub.subscriber_count += 1;
}

function decrement_subscriber_count(sub: StreamSubscription, user_id: number): void {
    const subscribers = get_loaded_subscriber_subset(sub.stream_id);
    // If we don't have full subscriber data, we assume that even if didn't know
    // they were a subscriber, we still want to decrement the count.
    if (fetched_stream_ids.has(sub.stream_id) && !subscribers.has(user_id)) {
        return;
    }
    sub.subscriber_count -= 1;
}

// Note: `subscriber_count` can sometimes be wrong due to races on the backend,
// so we should fetch full subscriber data if we care about this number being
// accurate.
export let get_subscriber_count = (stream_id: number, include_bots = true): number => {
    const sub = sub_store.get(stream_id);
    if (sub === undefined) {
        blueslip.warn(`We called get_subscriber_count for an untracked stream: ${stream_id}`);
        return 0;
    }

    if (include_bots) {
        return sub.subscriber_count;
    }

    let bot_count = 0;
    for (const user_id of get_loaded_subscriber_subset(stream_id).keys()) {
        if (people.is_valid_bot_user(user_id)) {
            bot_count += 1;
        }
    }
    return sub.subscriber_count - bot_count;
};

export function rewire_get_subscriber_count(value: typeof get_subscriber_count): void {
    get_subscriber_count = value;
}

export function get_subscribers(stream_id: number): number[] {
    // This is our external interface for callers who just
    // want an array of user_ids who are subscribed to a stream.
    const subscribers = get_loaded_subscriber_subset(stream_id);

    return [...subscribers.keys()];
}

export async function get_all_subscribers(
    stream_id: number,
    retry_on_failure = true,
): Promise<number[] | null> {
    // This function parallels `get_subscribers` but ensures we include all
    // subscribers, possibly fetching that data from the server.
    const subscribers = await get_full_subscriber_set(stream_id, retry_on_failure);
    // This means the request failed, which can only happen if `retry_on_failure`
    // is false.
    if (subscribers === null) {
        return null;
    }
    return [...subscribers.keys()];
}

export function set_subscribers(stream_id: number, user_ids: number[], full_data = true): void {
    const subscribers = new LazySet(user_ids);
    stream_subscribers.set(stream_id, subscribers);
    const sub = sub_store.get(stream_id);
    if (!sub) {
        blueslip.warn(`We called set_subscribers for an untracked stream: ${stream_id}`);
    } else if (full_data) {
        sub.subscriber_count = subscribers.size;
    }
    if (full_data) {
        fetched_stream_ids.add(stream_id);
    }
}

export function add_subscriber(stream_id: number, user_id: number): void {
    // If stream_id/user_id are unknown to us, we will
    // still track it, but we will warn.
    const subscribers = get_loaded_subscriber_subset(stream_id);
    const person = people.maybe_get_user_by_id(user_id);
    if (person === undefined) {
        blueslip.warn(`We tried to add invalid subscriber: ${user_id}`);
    }
    const sub = sub_store.get(stream_id);
    // If the sub is undefined, we'll be raising a warning in
    // `get_loaded_subscriber_subset`, so we don't need to here.
    if (sub) {
        increment_subscriber_count(sub, user_id);
    }
    subscribers.add(user_id);
}

export function remove_subscriber(stream_id: number, user_id: number): void {
    const sub = sub_store.get(stream_id);
    // If the sub is undefined, we'll be raising a warning in
    // `get_loaded_subscriber_subset`, so we don't need to here.
    if (sub) {
        decrement_subscriber_count(sub, user_id);
    }
    const subscribers = get_loaded_subscriber_subset(stream_id);
    subscribers.delete(user_id);
}

export function bulk_add_subscribers({
    stream_ids,
    user_ids,
}: {
    stream_ids: number[];
    user_ids: number[];
}): void {
    // We rely on our callers to validate stream_ids and user_ids.
    for (const stream_id of stream_ids) {
        const subscribers = get_loaded_subscriber_subset(stream_id);
        const sub = sub_store.get(stream_id);
        for (const user_id of user_ids) {
            // If the sub is undefined, we'll be raising a warning in
            // `get_loaded_subscriber_subset`, so we don't need to here.
            if (sub) {
                increment_subscriber_count(sub, user_id);
            }
            subscribers.add(user_id);
        }

        if (pending_subscriber_requests.has(stream_id)) {
            pending_subscriber_requests.get(stream_id)!.pending_peer_events.push({
                type: "peer_add",
                user_ids,
            });
        }
    }
}

export function bulk_remove_subscribers({
    stream_ids,
    user_ids,
}: {
    stream_ids: number[];
    user_ids: number[];
}): void {
    // We rely on our callers to validate stream_ids and user_ids.
    for (const stream_id of stream_ids) {
        const subscribers = get_loaded_subscriber_subset(stream_id);
        const sub = sub_store.get(stream_id);
        for (const user_id of user_ids) {
            // If the sub is undefined, we'll be raising a warning in
            // `get_loaded_subscriber_subset`, so we don't need to here.
            if (sub) {
                decrement_subscriber_count(sub, user_id);
            }
            subscribers.delete(user_id);
        }

        if (pending_subscriber_requests.has(stream_id)) {
            pending_subscriber_requests.get(stream_id)!.pending_peer_events.push({
                type: "peer_remove",
                user_ids,
            });
        }
    }
}

export function is_user_subscribed(stream_id: number, user_id: number): boolean {
    // Most callers should call stream_data.is_user_subscribed,
    // which does additional checks.

    const subscribers = get_loaded_subscriber_subset(stream_id);
    return subscribers.has(user_id);
}

// TODO: If the server sends us a list of users for whom we have complete data,
// we can use that to avoid waiting for the `get_full_subscriber_set` check. We'd
// like to add that optimization in the future.
export async function maybe_fetch_is_user_subscribed(
    stream_id: number,
    user_id: number,
    retry_on_failure: boolean,
): Promise<boolean | null> {
    const subscribers = await get_full_subscriber_set(stream_id, retry_on_failure);
    // This means the request failed. We will return `null` here if
    // we can't determine if this user is subscribed or not.
    if (subscribers === null) {
        const subscribers = get_loaded_subscriber_subset(stream_id);
        if (subscribers.has(user_id)) {
            return true;
        }
        return null;
    }
    return subscribers.has(user_id);
}

export async function get_unique_subscriber_count_for_streams(
    stream_ids: number[],
): Promise<number> {
    const valid_subscribers = new LazySet([]);
    const promises: Record<number, Promise<LazySet>> = {};
    for (const stream_id of stream_ids) {
        promises[stream_id] = get_full_subscriber_set(stream_id, true);
    }

    for (const stream_id of stream_ids) {
        // If it's `null`, that means a request failed and we don't know the
        // full subscribers set, so just use whatever we have already.
        const subscribers = await promises[stream_id]!;

        for (const user_id of subscribers.keys()) {
            if (!people.is_valid_bot_user(user_id)) {
                valid_subscribers.add(user_id);
            }
        }
    }
    return valid_subscribers.size;
}
