var stream_muting = (function () {

var exports = {};

exports.update_in_home_view = function (sub, value) {
    // value is true if we are in home view
    // TODO: flip the semantics to be is_muting
    sub.in_home_view = value;

    setTimeout(function () {
        var msg_offset;
        var saved_ypos;
        // Save our current scroll position
        if (overlays.is_active()) {
            saved_ypos = message_viewport.scrollTop();
        } else if (home_msg_list === current_msg_list &&
                   current_msg_list.selected_row().offset() !== null) {
            msg_offset = current_msg_list.selected_row().offset().top;
        }

        home_msg_list.clear({clear_selected_id: false});

        // Recreate the home_msg_list with the newly filtered message_list.all
        message_util.add_old_messages(message_list.all.all_messages(), home_msg_list);

        // Ensure we're still at the same scroll position
        if (overlays.is_active()) {
            message_viewport.scrollTop(saved_ypos);
        } else if (home_msg_list === current_msg_list) {
            // We pass use_closest to handle the case where the
            // currently selected message is being hidden from the
            // home view
            home_msg_list.select_id(home_msg_list.selected_id(),
                                    {use_closest: true, empty_ok: true});
            if (current_msg_list.selected_id() !== -1) {
                current_msg_list.view.set_message_offset(msg_offset);
            }
        }

        // In case we added messages to what's visible in the home view, we need to re-scroll to
        // make sure the pointer is still visible. We don't want the auto-scroll handler to move
        // our pointer to the old scroll location before we have a chance to update it.
        pointer.recenter_pointer_on_display = true;
        pointer.suppress_scroll_pointer_update = true;

        if (!home_msg_list.empty()) {
            message_util.do_unread_count_updates(home_msg_list.all_messages());
        }
    }, 0);

    stream_list.set_in_home_view(sub.stream_id, sub.in_home_view);

    var not_in_home_view_checkbox = $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] #sub_setting_not_in_home_view .sub_setting_control");
    not_in_home_view_checkbox.prop('checked', !value);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_muting;
}

window.stream_muting = stream_muting;
