import * as channel from "./channel";
import * as settings_ui from "./settings_ui";
import * as sub_store from "./sub_store";

export function bulk_set_stream_property(sub_data, $status_element) {
    const url = "/json/users/me/subscriptions/properties";
    const data = {subscription_data: JSON.stringify(sub_data)};
    if (!$status_element) {
        return channel.post({
            url,
            data,
            timeout: 10 * 1000,
        });
    }

    settings_ui.do_settings_change(channel.post, url, data, $status_element);
    return undefined;
}

export function set_stream_property(sub, property, value, $status_element) {
    const sub_data = {stream_id: sub.stream_id, property, value};
    bulk_set_stream_property([sub_data], $status_element);
}

export function set_color(stream_id, color) {
    const sub = sub_store.get(stream_id);
    set_stream_property(sub, "color", color);
}
