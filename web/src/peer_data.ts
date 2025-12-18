import assert from "minimalistic-assert";
import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import {LazySet} from "./lazy_set.ts";
import {page_params} from "./page_params.ts";
import type {User} from "./people.ts";
import * as people from "./people.ts";
import * as sub_store from "./sub_store.ts";
import * as util from "./util.ts";

// Maps stream_id to the number of subscribers in that stream.
// Note: These counts can sometimes be wrong due to races on the backend,
// so we should fetch full subscriber data for a stream if we care about
// its count being accurate.
const subscriber_counts = new Map<number, number>();

const fetched_user_subscriptions = new Set<number>();

// This maps a stream_id to a LazySet of user_ids who are subscribed.
// We might not have all the subscribers for a given stream. Streams
// with full data will be stored in `fetched_stream_ids`, and for the
// rest we try to have all non-long-term-idle subscribers for streams,
// though that doesn't account for subscribers that become active after
// pageload.
// Make sure that when we have full subscriber data for a stream,
// the size of its subscribers set stays synced with the relevant
// stream's `subscriber_count`.
const stream_subscribers = new Map<number, LazySet>();
const fetched_stream_ids = new Set<number>();
export function has_full_subscriber_data(stream_id: number): boolean {
    return fetched_stream_ids.has(stream_id);
}

// Don't run this in loops, since it has O(channels) runtime.
export function has_complete_subscriber_data(): boolean {
    const all_stream_ids = new Set(sub_store.stream_ids());
    return (
        all_stream_ids.size === fetched_stream_ids.size &&
        all_stream_ids.difference(fetched_stream_ids).size === 0
    );
}

// Requests for subscribers of a stream
const pending_subscriber_requests = new Map<
    number,
    {
        // false means bad request, null means we retried too many times and gave up
        subscribers_promise: Promise<LazySet | null | false>;
        pending_peer_events: {
            type: "peer_add" | "peer_remove";
            user_ids: number[];
        }[];
    }
>();
// Requests for subscriptions for a user
const pending_subscription_requests = new Map<number, Promise<void>>();

export function clear_for_testing(): void {
    stream_subscribers.clear();
    fetched_stream_ids.clear();
    pending_subscriber_requests.clear();
    pending_subscription_requests.clear();
    fetched_user_subscriptions.clear();
}

const fetch_stream_subscribers_response_schema = z.object({
    subscribers: z.array(z.number()),
});

const fetch_user_subscriptions_response_schema = z.object({
    subscribed_channel_ids: z.array(z.number()),
});

// Warning: This function can fetch indefinitely (with longer retry
// delay each time) if the server keeps returning non-400 errors.
export async function fetch_stream_subscribers_with_retry(
    stream_id: number,
    num_attempts = 1,
): Promise<LazySet | null> {
    const subscribers = await fetch_stream_subscribers(stream_id);
    // Bad request, so just give up here.
    if (subscribers === false) {
        return null;
    }
    // Failed request, retry.
    if (subscribers === null) {
        num_attempts += 1;
        const retry_delay_secs = util.get_retry_backoff_seconds(undefined, num_attempts);
        await new Promise((resolve) => setTimeout(resolve, retry_delay_secs * 1000));
        return fetch_stream_subscribers_with_retry(stream_id, num_attempts);
    }
    return subscribers;
}

// This function either waits for an existing pending request or kicks off
// a new one.
export async function fetch_stream_subscribers(stream_id: number): Promise<LazySet | null | false> {
    if (pending_subscriber_requests.has(stream_id)) {
        return pending_subscriber_requests.get(stream_id)!.subscribers_promise;
    }
    pending_subscriber_requests.set(stream_id, {
        subscribers_promise: fetch_stream_subscribers_from_server(stream_id),
        pending_peer_events: [],
    });
    return pending_subscriber_requests.get(stream_id)!.subscribers_promise;
}

// This function wraps the fetch in a Promise so that we can have both
// the `channel.get` handling the xhr error and
// `fetch_stream_subscribers_from_server` not resolving until the success/error
// handling finishes.
async function fetch_stream_subscribers_from_server(
    stream_id: number,
): Promise<LazySet | null | false> {
    return new Promise<LazySet | null | false>((resolve) => {
        void channel.get({
            url: `/json/streams/${stream_id}/members`,
            success(result) {
                const fetched_subscribers =
                    fetch_stream_subscribers_response_schema.parse(result).subscribers;
                set_subscribers(stream_id, fetched_subscribers);
                const pending_peer_events =
                    pending_subscriber_requests.get(stream_id)!.pending_peer_events;
                pending_subscriber_requests.delete(stream_id);
                for (const event of pending_peer_events) {
                    if (event.type === "peer_add") {
                        bulk_add_subscribers({stream_ids: [stream_id], user_ids: event.user_ids});
                    } else {
                        bulk_remove_subscribers({
                            stream_ids: [stream_id],
                            user_ids: event.user_ids,
                        });
                    }
                }

                resolve(get_loaded_subscriber_subset(stream_id));
            },
            error(xhr) {
                pending_subscriber_requests.delete(stream_id);
                if (xhr.status === 400) {
                    blueslip.error("Bad request to fetch channel subscribers.", {
                        stream_id,
                        error_json: xhr.responseJSON,
                    });
                    resolve(false);
                } else {
                    blueslip.error("Failure fetching channel subscribers", {
                        stream_id,
                    });
                    resolve(null);
                }
            },
        });
    });
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
        let fetched_subscribers: LazySet | null | false;
        if (retry_on_failure) {
            fetched_subscribers = await fetch_stream_subscribers_with_retry(stream_id);
        } else {
            fetched_subscribers = await fetch_stream_subscribers(stream_id);
        }
        // This means a request failed and we don't know who the subscribers are.
        if (fetched_subscribers === null || fetched_subscribers === false) {
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

function increment_subscriber_count(
    subscribers: LazySet,
    stream_id: number,
    user_id: number,
): void {
    if (subscribers.has(user_id)) {
        return;
    }
    const subscriber_count = subscriber_counts.get(stream_id);
    if (subscriber_count === undefined) {
        blueslip.error(
            `We called increment_subscriber_count for an untracked stream: ${stream_id}`,
        );
    } else {
        subscriber_counts.set(stream_id, subscriber_count + 1);
    }
}

function decrement_subscriber_count(
    subscribers: LazySet,
    stream_id: number,
    user_id: number,
): void {
    // If we don't have full subscriber data, we assume that even if didn't know
    // they were a subscriber, we still want to decrement the count.
    if (fetched_stream_ids.has(stream_id) && !subscribers.has(user_id)) {
        return;
    }
    const subscriber_count = subscriber_counts.get(stream_id);
    if (subscriber_count === undefined) {
        blueslip.error(
            `We called decrement_subscriber_count for an untracked stream: ${stream_id}`,
        );
    } else {
        subscriber_counts.set(stream_id, subscriber_count - 1);
    }
}

// Note: `subscriber_count` can sometimes be wrong due to races on the backend,
// so we should fetch full subscriber data if we care about this number being
// accurate.
export let get_subscriber_count = (stream_id: number, include_bots = true): number => {
    const count = subscriber_counts.get(stream_id);
    if (count === undefined) {
        blueslip.warn(`We called get_subscriber_count for an untracked stream: ${stream_id}`);
        return 0;
    }

    if (include_bots) {
        return count;
    }

    let bot_count = 0;
    for (const user_id of get_loaded_subscriber_subset(stream_id).keys()) {
        if (people.is_valid_bot_user(user_id)) {
            bot_count += 1;
        }
    }
    return count - bot_count;
};

export function rewire_get_subscriber_count(value: typeof get_subscriber_count): void {
    get_subscriber_count = value;
}

export function set_subscriber_count(stream_id: number, count: number): void {
    subscriber_counts.set(stream_id, count);
}

export function clear_subscriber_counts_for_tests(): void {
    subscriber_counts.clear();
}

export function get_subscriber_ids_assert_loaded(stream_id: number): number[] {
    // TODO: Convert this to an `assert` once we can be more sure that this never
    // happens.
    if (!fetched_stream_ids.has(stream_id)) {
        blueslip.error("Getting subscribers for stream without full subscriber data", {
            stream_id,
        });
    }

    // This is our external interface for callers who just
    // want an array of user_ids who are subscribed to a stream.
    const subscribers = get_loaded_subscriber_subset(stream_id);

    return [...subscribers.keys()];
}

export async function get_subscribers_with_possible_fetch(
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
        subscriber_counts.set(stream_id, subscribers.size);
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
    increment_subscriber_count(subscribers, stream_id, user_id);
    subscribers.add(user_id);
}

export function remove_subscriber(stream_id: number, user_id: number): void {
    const subscribers = get_loaded_subscriber_subset(stream_id);
    decrement_subscriber_count(subscribers, stream_id, user_id);
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
                increment_subscriber_count(subscribers, sub.stream_id, user_id);
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
                decrement_subscriber_count(subscribers, sub.stream_id, user_id);
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

export function is_user_loaded_and_subscribed(stream_id: number, user_id: number): boolean {
    // Most callers should call stream_data.is_user_loaded_and_subscribed,
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

// This function wraps the fetch in a Promise so that we can have both
// the `channel.get` handling the xhr error and `load_subscriptions_for_user`
// not resolving until the success/error handling finishes.
async function fetch_subscriptions_for_user_from_server(user_id: number): Promise<boolean | null> {
    return new Promise<boolean | null>((resolve) => {
        channel.get({
            url: `/json/users/${user_id}/channels`,
            success(raw_data) {
                const subscriptions =
                    fetch_user_subscriptions_response_schema.parse(raw_data).subscribed_channel_ids;
                for (const stream_id of subscriptions) {
                    add_subscriber(stream_id, user_id);
                }
                fetched_user_subscriptions.add(user_id);
                resolve(true);
            },
            error(xhr) {
                if (xhr.status === 400) {
                    blueslip.error("Bad request to fetch user's subscribed channels.", {
                        user_id,
                        error_json: xhr.responseJSON,
                    });
                    resolve(false);
                } else {
                    resolve(null);
                }
            },
        });
    });
}

// This function might retry up to 5 times to fetch data, then will give up.
// We store the whole fetch with retry promise in the pending requests because
// there are no outside calls to fetch_subscriptions_for_user (without retry).
export async function fetch_subscriptions_for_user(user_id: number): Promise<void> {
    if (subscriber_data_loaded_for_user(user_id)) {
        return;
    }

    if (pending_subscription_requests.has(user_id)) {
        return pending_subscription_requests.get(user_id)!;
    }

    const subscriptions_promise = (async () => {
        let num_attempts = 0;
        while (num_attempts < 5) {
            if (num_attempts > 0) {
                blueslip.warn("Failure fetching user's subscribed channels. Retrying.", {
                    user_id,
                });
            }
            const result = await fetch_subscriptions_for_user_from_server(user_id);
            // Bad request, so just give up here.
            if (result === false) {
                pending_subscription_requests.delete(user_id);
                break;
            }
            // Failed request, so try again (unless we've reached the retry limit)
            else if (result === null) {
                num_attempts += 1;
                const retry_delay_secs = util.get_retry_backoff_seconds(undefined, num_attempts);
                await new Promise((resolve) => setTimeout(resolve, retry_delay_secs * 1000));
                continue;
            }
            // Success
            else {
                pending_subscription_requests.delete(user_id);
                break;
            }
        }
        if (num_attempts === 5) {
            blueslip.error("Failure fetching user's subscribed channels. Giving up.", {
                user_id,
            });
        }
    })();

    pending_subscription_requests.set(user_id, subscriptions_promise);
    return subscriptions_promise;
}

export function subscriber_data_loaded_for_user(user_id: number): boolean {
    return has_complete_subscriber_data() || fetched_user_subscriptions.has(user_id);
}
