var stream_events = (function () {

var exports = {};

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

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_events;
}
