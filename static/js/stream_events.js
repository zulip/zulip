var stream_events = (function () {

var exports = {};

function get_color() {
    var used_colors = stream_data.get_colors();
    var color = stream_color.pick_color(used_colors);
    return color;
}

function update_stream_desktop_notifications(sub, value) {
    var desktop_notifications_checkbox = $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #sub_desktop_notifications_setting .sub_setting_control");
    desktop_notifications_checkbox.prop('checked', value);
    sub.desktop_notifications = value;
}

function update_stream_audible_notifications(sub, value) {
    var audible_notifications_checkbox = $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #sub_audible_notifications_setting .sub_setting_control");
    audible_notifications_checkbox.prop('checked', value);
    sub.audible_notifications = value;
}

function update_stream_push_notifications(sub, value) {
    var push_notifications_checkbox = $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #sub_push_notifications_setting .sub_setting_control");
    push_notifications_checkbox.prop('checked', value);
    sub.push_notifications = value;
}

function update_stream_pin(sub, value) {
    var pin_checkbox = $('#pinstream-' + sub.stream_id);
    pin_checkbox.prop('checked', value);
    sub.pin_to_top = value;
}

exports.update_property = function (stream_id, property, value) {
    var sub = stream_data.get_sub_by_id(stream_id);
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
        stream_muting.update_in_home_view(sub, value);
        break;
    case 'desktop_notifications':
        update_stream_desktop_notifications(sub, value);
        break;
    case 'audible_notifications':
        update_stream_audible_notifications(sub, value);
        break;
    case 'push_notifications':
        update_stream_push_notifications(sub, value);
        break;
    case 'name':
        subs.update_stream_name(sub, value);
        break;
    case 'description':
        subs.update_stream_description(sub, value);
        break;
    case 'email_address':
        sub.email_address = value;
        break;
    case 'pin_to_top':
        update_stream_pin(sub, value);
        stream_list.refresh_pinned_or_unpinned_stream(sub);
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
    if (color !== undefined) {
        sub.color = color;
    } else if (sub.color === undefined) {
        // If the backend didn't, and we have a color already, send
        // the backend that color.  It's not clear this code path is
        // needed.
        blueslip.warn("Frontend needed to pick a color in mark_subscribed");
        color = get_color();
        subs.set_color(sub.stream_id, color);
    }
    stream_data.subscribe_myself(sub);
    if (subscribers) {
        stream_data.set_subscriber_emails(sub, subscribers);
    }

    subs.update_settings_for_subscribed(sub);

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        current_msg_list.update_trailing_bookend();
    }

    // Update unread counts as the new stream in sidebar might
    // need its unread counts re-calculated
    message_util.do_unread_count_updates(message_list.all.all_messages());

    $(document).trigger($.Event('subscription_add_done.zulip', {sub: sub}));
};

exports.mark_unsubscribed = function (sub) {
    if (sub === undefined) {
        // We don't know about this stream
        return;
    } else if (sub.subscribed) {
        stream_data.unsubscribe_myself(sub);

        subs.update_settings_for_unsubscribed(sub);

    } else {
        // Already unsubscribed
        return;
    }

    if (narrow_state.is_for_stream_id(sub.stream_id)) {
        current_msg_list.update_trailing_bookend();
    }

    $(document).trigger($.Event('subscription_remove_done.zulip', {sub: sub}));
};


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_events;
}
