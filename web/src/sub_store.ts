import * as v from "valibot";

import * as blueslip from "./blueslip.ts";
import type {
    never_subscribed_stream_schema,
    stream_properties_schema,
    stream_schema,
    stream_specific_notification_settings_schema,
} from "./stream_types.ts";
import {api_stream_subscription_schema} from "./stream_types.ts";

export type Stream = v.InferOutput<typeof stream_schema>;
export type StreamSpecificNotificationSettings = v.InferOutput<
    typeof stream_specific_notification_settings_schema
>;
export type NeverSubscribedStream = v.InferOutput<typeof never_subscribed_stream_schema>;
export type StreamProperties = v.InferOutput<typeof stream_properties_schema>;
export type ApiStreamSubscription = v.InferOutput<typeof api_stream_subscription_schema>;

// This is the actual type of subscription objects we use in the app.
export const stream_subscription_schema = v.object({
    ...v.omit(api_stream_subscription_schema, ["subscribers"]).entries,
    // These properties are added in `stream_data` when hydrating the streams and are not present in the data we get from the server.
    render_subscribers: v.boolean(),
    newly_subscribed: v.boolean(),
    subscribed: v.boolean(),
    previously_subscribed: v.boolean(),
});
export type StreamSubscription = v.InferOutput<typeof stream_subscription_schema>;

const subs_by_stream_id = new Map<number, StreamSubscription>();

export let get = (stream_id: number): StreamSubscription | undefined =>
    subs_by_stream_id.get(stream_id);

export function rewire_get(value: typeof get): void {
    get = value;
}

export function validate_stream_ids(stream_ids: number[]): number[] {
    const good_ids = [];
    const bad_ids = [];

    for (const stream_id of stream_ids) {
        if (subs_by_stream_id.has(stream_id)) {
            good_ids.push(stream_id);
        } else {
            bad_ids.push(stream_id);
        }
    }

    if (bad_ids.length > 0) {
        blueslip.warn(`We have untracked stream_ids: ${bad_ids.toString()}`);
    }

    return good_ids;
}

export function clear(): void {
    subs_by_stream_id.clear();
}

export function add_hydrated_sub(stream_id: number, sub: StreamSubscription): void {
    // The only code that should call this directly is
    // in stream_data.js. Grep there to find callers.
    subs_by_stream_id.set(stream_id, sub);
}

export function maybe_get_stream_name(stream_id: number): string | undefined {
    if (!stream_id) {
        return undefined;
    }
    const stream = get(stream_id);

    if (!stream) {
        return undefined;
    }

    return stream.name;
}
