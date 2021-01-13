const {LazySet} = require("./lazy_set");
const people = require("./people");

/*

For legacy reasons this module is mostly tested
by frontend_tests/node_tests/stream_data.js.

*/

// This maps a stream_id to a LazySet of user_ids who are subscribed.
// We maintain the invariant that this has keys for all all stream_ids
// that we track in the other data structures.  We intialize it during
// clear_subscriptions.
let stream_subscribers;

export function clear() {
    stream_subscribers = new Map();
}

export function maybe_clear_subscribers(stream_id) {
    if (!stream_subscribers.has(stream_id)) {
        set_subscribers(stream_id, []);
    }
}

export function is_subscriber_subset(sub1, sub2) {
    const stream_id1 = sub1.stream_id;
    const stream_id2 = sub2.stream_id;

    const sub1_set = stream_subscribers.get(stream_id1);
    const sub2_set = stream_subscribers.get(stream_id2);

    if (sub1_set && sub2_set) {
        return Array.from(sub1_set.keys()).every((key) => sub2_set.has(key));
    }

    return false;
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

    const subscribers = stream_subscribers.get(stream_id);

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
    const subscribers = stream_subscribers.get(stream_id);

    if (!subscribers) {
        blueslip.warn("We got a get_subscriber_count call for an untracked stream: " + stream_id);
        return undefined;
    }

    return subscribers.size;
}

export function get_subscribers(stream_id) {
    const subscribers = stream_subscribers.get(stream_id);

    if (typeof subscribers === "undefined") {
        blueslip.warn("We called get_subscribers for an untracked stream: " + stream_id);
        return [];
    }

    return Array.from(subscribers.keys());
}

export function set_subscribers(stream_id, user_ids) {
    const subscribers = new LazySet(user_ids || []);
    stream_subscribers.set(stream_id, subscribers);
}

export function add_subscriber(stream_id, user_id) {
    const subscribers = stream_subscribers.get(stream_id);
    if (typeof subscribers === "undefined") {
        blueslip.warn("We got an add_subscriber call for an untracked stream: " + stream_id);
        return false;
    }
    const person = people.get_by_user_id(user_id);
    if (person === undefined) {
        blueslip.error("We tried to add invalid subscriber: " + user_id);
        return false;
    }
    subscribers.add(user_id);

    return true;
}

export function remove_subscriber(stream_id, user_id) {
    const subscribers = stream_subscribers.get(stream_id);
    if (typeof subscribers === "undefined") {
        blueslip.warn("We got a remove_subscriber call for an untracked stream " + stream_id);
        return false;
    }
    if (!subscribers.has(user_id)) {
        blueslip.warn("We tried to remove invalid subscriber: " + user_id);
        return false;
    }

    subscribers.delete(user_id);

    return true;
}

export function is_user_subscribed(stream_id, user_id) {
    // Most callers should call stream_data.is_user_subscribed,
    // which does additional checks.

    const subscribers = stream_subscribers.get(stream_id);
    if (typeof subscribers === "undefined") {
        blueslip.warn("We called is_user_subscribed for an untracked stream: " + stream_id);
        return false;
    }

    return subscribers.has(user_id);
}
