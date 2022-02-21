import * as channel from "./channel";

/*
    This module simply encapsulates our legacy API for subscribing
    or unsubscribing users from streams. Callers don't need to
    know the strange names of "subscriptions" and "principals",
    nor how to JSON.stringify things, nor the URL scheme.
*/

export function add_user_ids_to_stream(user_ids, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {
            subscriptions: JSON.stringify([{name: stream_name}]),
            principals: JSON.stringify(user_ids),
        },
        success,
        error: failure,
    });
}

export function remove_user_id_from_stream(user_id, sub, success, failure) {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream_name]), principals: JSON.stringify([user_id])},
        success,
        error: failure,
    });
}
