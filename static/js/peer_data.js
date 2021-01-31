const {LazySet} = require("./lazy_set");
const people = require("./people");

// This maps a stream_id to a LazySet of user_ids who are subscribed.
const stream_subscribers = new Map();

function assert_number(id) {
    if (typeof id !== "number") {
        blueslip.error(`You must pass ids as numbers to peer_data. id = ${id}`);
    }
}

function get_user_set(stream_id) {
    // This is an internal function to get the LazySet of users.
    // We create one on the fly as necessary, but we warn in that case.
    assert_number(stream_id);

    if (!stream_data.get_sub_by_id(stream_id)) {
        blueslip.warn("We called get_user_set for an untracked stream: " + stream_id);
    }

    let subscribers = stream_subscribers.get(stream_id);

    if (subscribers === undefined) {
        subscribers = new LazySet([]);
        stream_subscribers.set(stream_id, subscribers);
    }

    return subscribers;
}

export function is_subscriber_subset(stream_id1, stream_id2) {
    const sub1_set = get_user_set(stream_id1);
    const sub2_set = get_user_set(stream_id2);

    return Array.from(sub1_set.keys()).every((key) => sub2_set.has(key));
}

export function potential_subscribers(stream_id) {
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

    function is_potential_subscriber(person) {
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

export function get_subscriber_count(stream_id) {
    const subscribers = get_user_set(stream_id);
    return subscribers.size;
}

export function get_subscribers(stream_id) {
    // This is our external interface for callers who just
    // want an array of user_ids who are subscribed to a stream.
    const subscribers = get_user_set(stream_id);

    return Array.from(subscribers.keys());
}

export function set_subscribers(stream_id, user_ids) {
    const subscribers = new LazySet(user_ids || []);
    stream_subscribers.set(stream_id, subscribers);
}

export function add_subscriber(stream_id, user_id) {
    // If stream_id/user_id are unknown to us, we will
    // still track it, but we will warn.
    const subscribers = get_user_set(stream_id);
    const person = people.get_by_user_id(user_id);
    if (person === undefined) {
        blueslip.warn("We tried to add invalid subscriber: " + user_id);
    }
    subscribers.add(user_id);
}

export function remove_subscriber(stream_id, user_id) {
    const subscribers = get_user_set(stream_id);
    if (!subscribers.has(user_id)) {
        blueslip.warn("We tried to remove invalid subscriber: " + user_id);
        return false;
    }

    subscribers.delete(user_id);

    return true;
}

export function bulk_add_subscribers({stream_ids, user_ids}) {
    // We rely on our callers to validate stream_ids and user_ids.
    for (const stream_id of stream_ids) {
        const subscribers = get_user_set(stream_id);
        for (const user_id of user_ids) {
            subscribers.add(user_id);
        }
    }
}

export function bulk_remove_subscribers({stream_ids, user_ids}) {
    // We rely on our callers to validate stream_ids and user_ids.
    for (const stream_id of stream_ids) {
        const subscribers = get_user_set(stream_id);
        for (const user_id of user_ids) {
            subscribers.delete(user_id);
        }
    }
}

export function is_user_subscribed(stream_id, user_id) {
    // Most callers should call stream_data.is_user_subscribed,
    // which does additional checks.

    const subscribers = get_user_set(stream_id);
    return subscribers.has(user_id);
}
