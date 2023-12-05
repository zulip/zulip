import * as channel from "./channel";
import * as people from "./people";
import type { StreamSubscription } from "./sub_store";
/*
    This module simply encapsulates our legacy API for subscribing
    or unsubscribing users from streams. Callers don't need to
    know the strange names of "subscriptions" and "principals",
    nor how to JSON.stringify things, nor the URL scheme.
*/

//declaring type for the function parameters
type ids=number[];
type succ_type=()=>void;
type fail_type=(xhr:JQuery.jqXHR<unknown>)=>void;

export function add_user_ids_to_stream(user_ids:ids, sub:StreamSubscription, success:succ_type, failure:fail_type):JQuery.jqXHR<unknown> | undefined {
    // TODO: use stream_id when backend supports it
    const stream_name:string = sub.name;
    if (user_ids.length === 1 && people.is_my_user_id(Number(user_ids[0]))) {
        // Self subscribe
        const color:string = sub.color;
        return channel.post({
            url: "/json/users/me/subscriptions",
            data: {subscriptions: JSON.stringify([{name: stream_name, color}])},
            success,
            error: failure,
        });
    }
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

export function remove_user_id_from_stream(user_id:ids, sub:StreamSubscription, success:succ_type, failure:fail_type):JQuery.jqXHR<unknown> | undefined {
    // TODO: use stream_id when backend supports it
    const stream_name = sub.name;
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([stream_name]), principals: JSON.stringify([user_id])},
        success,
        error: failure,
    });
}
