// See https://zulip.readthedocs.io/en/latest/subsystems/pointer.html for notes on
// how this system is designed.

exports.recenter_pointer_on_display = false;
exports.set_recenter_pointer_on_display = function (value) {
    exports.recenter_pointer_on_display = value;
};

// Toggles re-centering the pointer in the window
// when All Messages is next clicked by the user
exports.suppress_scroll_pointer_update = false;
exports.set_suppress_scroll_pointer_update = function (value) {
    exports.suppress_scroll_pointer_update = value;
};
exports.furthest_read = -1;
exports.set_furthest_read = function (value) {
    exports.furthest_read = value;
};
exports.server_furthest_read = -1;
exports.set_server_furthest_read = function (value) {
    exports.server_furthest_read = value;
};

var pointer_update_in_flight = false;

function update_pointer() {
    if (!pointer_update_in_flight) {
        pointer_update_in_flight = true;
        return channel.post({
            url: '/json/users/me/pointer',
            idempotent: true,
            data: {pointer: exports.furthest_read},
            success: function () {
                exports.server_furthest_read = exports.furthest_read;
                pointer_update_in_flight = false;
            },
            error: function () {
                pointer_update_in_flight = false;
            },
        });
    }
    // Return an empty, resolved Deferred.
    return $.when();
}


exports.send_pointer_update = function () {
    // Only bother if you've read new messages.
    if (exports.furthest_read > exports.server_furthest_read) {
        update_pointer();
    }
};

function unconditionally_send_pointer_update() {
    if (pointer_update_in_flight) {
        // Keep trying.
        var deferred = $.Deferred();

        setTimeout(function () {
            deferred.resolve(unconditionally_send_pointer_update());
        }, 100);
        return deferred;
    }
    return update_pointer();
}

exports.fast_forward_pointer = function () {
    channel.get({
        url: '/json/users/me',
        idempotent: true,
        success: function (data) {
            unread_ops.mark_all_as_read(function () {
                exports.furthest_read = data.max_message_id;
                unconditionally_send_pointer_update().then(function () {
                    reload.initiate({immediate: true,
                                     save_pointer: false,
                                     save_narrow: true,
                                     save_compose: true});
                });
            });
        },
    });
};

exports.initialize = function initialize() {
    exports.server_furthest_read = page_params.pointer;
    if (page_params.orig_initial_pointer !== undefined &&
        page_params.orig_initial_pointer > exports.server_furthest_read) {
        exports.server_furthest_read = page_params.orig_initial_pointer;
    }
    exports.furthest_read = exports.server_furthest_read;

    // We only send pointer updates when the user has been idle for a
    // short while to avoid hammering the server
    $(document).idle({idle: 1000,
                      onIdle: exports.send_pointer_update,
                      keepTracking: true});

    $(document).on('message_selected.zulip', function (event) {
        // Only advance the pointer when not narrowed
        if (event.id === -1) {
            return;
        }
        // Additionally, don't advance the pointer server-side
        // if the selected message is local-only
        if (event.msg_list === home_msg_list && page_params.narrow_stream === undefined) {
            if (event.id > exports.furthest_read) {
                var msg = home_msg_list.get(event.id);
                if (!msg.locally_echoed) {
                    exports.furthest_read = event.id;
                }
            }
        }

        if (event.mark_read && event.previously_selected !== -1) {
            // Mark messages between old pointer and new pointer as read
            var messages;
            if (event.id < event.previously_selected) {
                messages = event.msg_list.message_range(event.id, event.previously_selected);
            } else {
                messages = event.msg_list.message_range(event.previously_selected, event.id);
            }
            if (event.msg_list.can_mark_messages_read()) {
                unread_ops.notify_server_messages_read(messages, {from: 'pointer'});
            }
        }
    });
};

window.pointer = exports;
