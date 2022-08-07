import $ from "jquery";

import {all_messages_data} from "./all_messages_data";
import * as blueslip from "./blueslip";
import * as color_data from "./color_data";
import * as message_lists from "./message_lists";
import * as message_util from "./message_util";
import * as message_view_header from "./message_view_header";
import * as narrow_state from "./narrow_state";
import * as overlays from "./overlays";
import * as peer_data from "./peer_data";
import * as recent_topics_ui from "./recent_topics_ui";
import * as settings_notifications from "./settings_notifications";
import * as stream_color from "./stream_color";
import * as stream_data from "./stream_data";
import * as stream_list from "./stream_list";
import * as stream_muting from "./stream_muting";
import * as stream_settings_ui from "./stream_settings_ui";
import * as sub_store from "./sub_store";

// In theory, this function should apply the account-level defaults,
// however, they are only called after a manual override, so
// doing so is unnecessary with the current code.  Ideally, we'd do a
// refactor to address that, however.
function update_stream_setting(sub, value, setting) {
    const $setting_checkbox = $(`#${CSS.escape(setting)}_${CSS.escape(sub.stream_id)}`);
    $setting_checkbox.prop("checked", value);
    sub[setting] = value;
}

export function update_property(stream_id, property, value, other_values) {
    const sub = sub_store.get(stream_id);
    if (sub === undefined) {
        // This isn't a stream we know about, so ignore it.
        blueslip.warn("Update for an unknown subscription", {
            stream_id,
            property,
            value,
        });
        return;
    }

    switch (property) {
        case "color":
            stream_color.update_stream_color(sub, value, {update_historical: true});
            break;
        case "in_home_view":
            stream_muting.update_is_muted(sub, !value);
            stream_list.refresh_muted_or_unmuted_stream(sub);
            recent_topics_ui.complete_rerender();
            break;
        case "desktop_notifications":
        case "audible_notifications":
        case "push_notifications":
        case "email_notifications":
        case "wildcard_mentions_notify":
            update_stream_setting(sub, value, property);
            settings_notifications.update_page(settings_notifications.user_settings_panel);
            break;
        case "name":
            stream_settings_ui.update_stream_name(sub, value);
            break;
        case "description":
            stream_settings_ui.update_stream_description(
                sub,
                value,
                other_values.rendered_description,
            );
            break;
        case "email_address":
            sub.email_address = value;
            break;
        case "pin_to_top":
            update_stream_setting(sub, value, property);
            stream_list.refresh_pinned_or_unpinned_stream(sub);
            break;
        case "invite_only":
            stream_settings_ui.update_stream_privacy(sub, {
                invite_only: value,
                history_public_to_subscribers: other_values.history_public_to_subscribers,
                is_web_public: other_values.is_web_public,
            });
            break;
        case "stream_post_policy":
            stream_settings_ui.update_stream_post_policy(sub, value);
            break;
        case "message_retention_days":
            stream_settings_ui.update_message_retention_setting(sub, value);
            break;
        default:
            blueslip.warn("Unexpected subscription property type", {
                property,
                value,
            });
    }
}

// Add yourself to a stream we already know about client-side.
// It's likely we should be passing in the full sub object from the caller/backend,
// but for now we just pass in the subscribers and color (things likely to be different).
export function mark_subscribed(sub, subscribers, color) {
    if (sub === undefined) {
        blueslip.error("Undefined sub passed to mark_subscribed");
        return;
    }

    if (sub.subscribed) {
        return;
    }

    // If the backend sent us a color, use that
    if (color !== undefined && sub.color !== color) {
        sub.color = color;
        stream_color.update_stream_color(sub, color, {update_historical: true});
    } else if (sub.color === undefined) {
        // If the backend didn't, and we have a color already, send
        // the backend that color.  It's not clear this code path is
        // needed.
        blueslip.warn("Frontend needed to pick a color in mark_subscribed");
        color = color_data.pick_color();
        stream_settings_ui.set_color(sub.stream_id, color);
    }
    stream_data.subscribe_myself(sub);
    if (subscribers) {
        peer_data.set_subscribers(sub.stream_id, subscribers);
    }

    if (overlays.streams_open()) {
        stream_settings_ui.update_settings_for_subscribed(sub);
    }

    // update navbar if necessary
    message_view_header.maybe_rerender_title_area_for_stream(sub);

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        message_lists.current.update_trailing_bookend();
    }

    // Update unread counts as the new stream in sidebar might
    // need its unread counts re-calculated
    message_util.do_unread_count_updates(all_messages_data.all_messages());

    stream_list.add_sidebar_row(sub);
}

export function mark_unsubscribed(sub) {
    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
        stream_data.unsubscribe_myself(sub);
        if (overlays.streams_open()) {
            stream_settings_ui.update_settings_for_unsubscribed(sub);
        }
        // update navbar if necessary
        message_view_header.maybe_rerender_title_area_for_stream(sub);
    } else {
        // Already unsubscribed
        return;
    }

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        message_lists.current.update_trailing_bookend();
    }

    stream_list.remove_sidebar_row(sub.stream_id);
}

export function remove_deactivated_user_from_all_streams(user_id) {
    const all_subs = stream_data.get_unsorted_subs();

    for (const sub of all_subs) {
        if (stream_data.is_user_subscribed(sub.stream_id, user_id)) {
            peer_data.remove_subscriber(sub.stream_id, user_id);
            stream_settings_ui.update_subscribers_ui(sub);
        }
    }
}
