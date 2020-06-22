// In theory, this function should apply the account-level defaults,
// however, they are only called after a manual override, so
// doing so is unnecessary with the current code.  Ideally, we'd do a
// refactor to address that, however.
function update_stream_setting(sub, value, setting) {
    const setting_checkbox = $("#" + setting + "_" + sub.stream_id);
    setting_checkbox.prop("checked", value);
    sub[setting] = value;
}

exports.update_property = function (stream_id, property, value, other_values) {
    const sub = stream_data.get_sub_by_id(stream_id);
    if (sub === undefined) {
        // This isn't a stream we know about, so ignore it.
        blueslip.warn("Update for an unknown subscription", {stream_id: stream_id,
                                                             property: property,
                                                             value: value});
        return;
    }

    switch (property) {
    case 'color':
        stream_color.update_stream_color(sub, value, {update_historical: true});
        break;
    case 'in_home_view':
        stream_muting.update_is_muted(sub, !value);
        break;
    case 'desktop_notifications':
    case 'audible_notifications':
    case 'push_notifications':
    case 'email_notifications':
    case 'wildcard_mentions_notify':
        update_stream_setting(sub, value, property);
        settings_notifications.update_page();
        break;
    case 'name':
        subs.update_stream_name(sub, value);
        break;
    case 'description':
        subs.update_stream_description(sub, value, other_values.rendered_description);
        break;
    case 'email_address':
        sub.email_address = value;
        break;
    case 'pin_to_top':
        update_stream_setting(sub, value, property);
        stream_list.refresh_pinned_or_unpinned_stream(sub);
        break;
    case 'invite_only':
        subs.update_stream_privacy(sub, {
            invite_only: value,
            history_public_to_subscribers: other_values.history_public_to_subscribers,
        });
        break;
    case 'stream_post_policy':
        subs.update_stream_post_policy(sub, value);
        break;
    case 'message_retention_days':
        subs.update_message_retention_setting(sub, value);
        break;
    default:
        blueslip.warn("Unexpected subscription property type", {property: property,
                                                                value: value});
    }
};

// Add yourself to a stream we already know about client-side.
// It's likely we should be passing in the full sub object from the caller/backend,
// but for now we just pass in the subscribers and color (things likely to be different).
exports.mark_subscribed = function (sub, subscribers, color) {
    if (sub === undefined) {
        blueslip.error('Undefined sub passed to mark_subscribed');
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
        subs.set_color(sub.stream_id, color);
    }
    stream_data.subscribe_myself(sub);
    if (subscribers) {
        stream_data.set_subscribers(sub, subscribers);
    }
    stream_data.update_calculated_fields(sub);

    if (overlays.streams_open()) {
        subs.update_settings_for_subscribed(sub);
    }

    // update navbar if necessary
    tab_bar.maybe_rerender_title_area_for_stream(sub);

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        current_msg_list.update_trailing_bookend();
    }

    // Update unread counts as the new stream in sidebar might
    // need its unread counts re-calculated
    message_util.do_unread_count_updates(message_list.all.all_messages());

    stream_list.add_sidebar_row(sub);
};

exports.mark_unsubscribed = function (sub) {
    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
        stream_data.unsubscribe_myself(sub);
        stream_data.update_calculated_fields(sub);
        if (overlays.streams_open()) {
            subs.update_settings_for_unsubscribed(sub);
        }
        // update navbar if necessary
        tab_bar.maybe_rerender_title_area_for_stream(sub);
    } else {
        // Already unsubscribed
        return;
    }

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        current_msg_list.update_trailing_bookend();
    }

    stream_list.remove_sidebar_row(sub.stream_id);
};

exports.remove_deactivated_user_from_all_streams = function (user_id) {
    const all_subs = stream_data.get_unsorted_subs();

    for (const sub of all_subs) {
        if (stream_data.is_user_subscribed(sub.name, user_id)) {
            stream_data.remove_subscriber(sub.stream_id, user_id);
            subs.update_subscribers_ui(sub);
        }
    }
};


window.stream_events = exports;
