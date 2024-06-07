import * as blueslip from "./blueslip";
import {LazySet} from "./lazy_set";
import type {User} from "./people";
import * as people from "./people";
import * as sub_store from "./sub_store";

// This maps a stream_id to a LazySet of user_ids who are subscribed.
const stream_subscribers = new Map<number, LazySet>();

export const clear_for_testing = (): void => {
    stream_subscribers.clear();
};

const get_user_set = (stream_id: number): LazySet => {
    // This is an internal function to get the LazySet of users.
    // We create one on the fly as necessary, but we warn in that case.
    if (!sub_store.get(stream_id)) {
        blueslip.warn(`We called get_user_set for an untracked stream: ${stream_id}`);
    }

    let subscribers = stream_subscribers.get(stream_id);

    if (subscribers === undefined) {
        subscribers = new LazySet([]);
        stream_subscribers.set(stream_id, subscribers);
    }

    return subscribers;
};

export const is_subscriber_subset = (stream_id1: number, stream_id2: number): boolean => {
    const sub1_set = get_user_set(stream_id1);
    const sub2_set = get_user_set(stream_id2);

    return [...sub1_set.keys()].every((key) => sub2_set.has(key));
};

export const potential_subscribers = (stream_id: number): User[] => {
    /*
        This is a list of unsubscribed users
        for the current stream, who the current
        user could potentially subscribe to the
        stream.  This may include some bots.

        We currently use it for typeahead in
        stream_edit.js.

        This may be a superset of the actual
        subscribers that you can change in some cases
        (like if you're a guest?); we should refine this
        going forward, especially if we use it for something
        other than typeahead.  (The guest use case
        may be moot now for other reasons.)
    */

    const subscribers = get_user_set(stream_id);

    const is_potential_subscriber = (person: User): boolean => {
        // Use verbose style to force better test
        // coverage, plus we may add more conditions over
        // time.
        if (subscribers.has(person.user_id)) {
            return false;
        }

        return true;
    };

    return people.filter_all_users(is_potential_subscriber);
};

export const get_subscriber_count = (stream_id: number, include_bots = true): number => {
    if (include_bots) {
        return get_user_set(stream_id).size;
    }

    let count = 0;
    for (const user_id of get_user_set(stream_id).keys()) {
        if (!people.is_valid_bot_user(user_id)) {
            count += 1;
        }
    }
    return count;
};

export const get_subscribers = (stream_id: number): number[] => {
    // This is our external interface for callers who just
    // want an array of user_ids who are subscribed to a stream.
    const subscribers = get_user_set(stream_id);

    return [...subscribers.keys()];
};

export const set_subscribers = (stream_id: number, user_ids: number[]): void => {
    const subscribers = new LazySet(user_ids);
    stream_subscribers.set(stream_id, subscribers);
};

export const add_subscriber = (stream_id: number, user_id: number): void => {
    // If stream_id/user_id are unknown to us, we will
    // still track it, but we will warn.
    const subscribers = get_user_set(stream_id);
    const person = people.maybe_get_user_by_id(user_id);
    if (person === undefined) {
        blueslip.warn(`We tried to add invalid subscriber: ${user_id}`);
    }
    subscribers.add(user_id);
};

export const remove_subscriber = (stream_id: number, user_id: number): boolean => {
    const subscribers = get_user_set(stream_id);
    if (!subscribers.has(user_id)) {
        blueslip.warn(`We tried to remove invalid subscriber: ${user_id}`);
        return false;
    }

    subscribers.delete(user_id);

    return true;
};

export const bulk_add_subscribers = ({
    stream_ids,
    user_ids,
}: {
    stream_ids: number[];
    user_ids: number[];
}): void => {
    // We rely on our callers to validate stream_ids and user_ids.
    for (const stream_id of stream_ids) {
        const subscribers = get_user_set(stream_id);
        for (const user_id of user_ids) {
            subscribers.add(user_id);
        }
    }
};

export const bulk_remove_subscribers = ({
    stream_ids,
    user_ids,
}: {
    stream_ids: number[];
    user_ids: number[];
}): void => {
    // We rely on our callers to validate stream_ids and user_ids.
    for (const stream_id of stream_ids) {
        const subscribers = get_user_set(stream_id);
        for (const user_id of user_ids) {
            subscribers.delete(user_id);
        }
    }
};

export const is_user_subscribed = (stream_id: number, user_id: number): boolean => {
    // Most callers should call stream_data.is_user_subscribed,
    // which does additional checks.

    const subscribers = get_user_set(stream_id);
    return subscribers.has(user_id);
};
