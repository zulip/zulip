import * as channel from "./channel.ts";
import * as settings_ui from "./settings_ui.ts";
import type {StreamProperties, StreamSubscription} from "./sub_store.ts";

export type SubData = {
    [Property in keyof StreamProperties]: {
        stream_id: number;
        property: Property;
        value: StreamProperties[Property];
    };
}[keyof StreamProperties][];

export function bulk_set_stream_property(sub_data: SubData, $status_element?: JQuery): void {
    const url = "/json/users/me/subscriptions/properties";
    const data = {subscription_data: JSON.stringify(sub_data)};
    if (!$status_element) {
        return void channel.post({
            url,
            data,
            timeout: 10 * 1000,
        });
    }

    settings_ui.do_settings_change(channel.post, url, data, $status_element);
    return undefined;
}

export function set_stream_property(
    sub: StreamSubscription,
    data: {
        [Property in keyof StreamProperties]: {
            property: Property;
            value: StreamProperties[Property];
        };
    }[keyof StreamProperties],
    $status_element?: JQuery,
): void {
    const sub_data = {stream_id: sub.stream_id, ...data};
    bulk_set_stream_property([sub_data], $status_element);
}

export function set_color(stream_id: number, color: string | null): void {
    const data = {
        subscription_data: JSON.stringify([{stream_id, property: "color", value: color}]),
    };
    void channel.post({url: "/json/users/me/subscriptions/properties", data});
}

export function set_default_color(
    stream_id: number,
    color: string | null,
    $status_element?: JQuery,
): void {
    const url = `/json/streams/${stream_id}`;
    const data = {default_color: JSON.stringify(color)};
    if ($status_element) {
        settings_ui.do_settings_change(channel.patch, url, data, $status_element);
    } else {
        void channel.patch({url, data});
    }
}
