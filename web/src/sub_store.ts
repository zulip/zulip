import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import type {
    never_subscribed_stream_schema,
    stream_properties_schema,
    stream_schema,
    stream_specific_notification_settings_schema,
} from "./stream_types.ts";
import {api_stream_subscription_schema} from "./stream_types.ts";

export type Stream = z.infer<typeof stream_schema>;
export type StreamSpecificNotificationSettings = z.infer<
    typeof stream_specific_notification_settings_schema
>;
export type NeverSubscribedStream = z.infer<typeof never_subscribed_stream_schema>;
export type StreamProperties = z.infer<typeof stream_properties_schema>;
export type ApiStreamSubscription = z.infer<typeof api_stream_subscription_schema>;

// This is the actual type of subscription objects we use in the app.
export const stream_subscription_schema = z.object({
    ...z.omit(api_stream_subscription_schema, {
        subscribers: true,
    }).shape,
    // These properties are added in `stream_data` when hydrating the streams and are not present in the data we get from the server.
    render_subscribers: z.boolean(),
    newly_subscribed: z.boolean(),
    subscribed: z.boolean(),
    previously_subscribed: z.boolean(),
});
export type StreamSubscription = z.infer<typeof stream_subscription_schema>;

const subs_by_stream_id = new Map<number, StreamSubscription>();

export function get(stream_id: number): StreamSubscription | undefined {
    return subs_by_stream_id.get(stream_id);
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

export function delete_sub(stream_id: number): void {
    subs_by_stream_id.delete(stream_id);
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
