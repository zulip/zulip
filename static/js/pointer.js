var pointer = (function () {

var exports = {};

exports.recenter_pointer_on_display = false;

// Toggles re-centering the pointer in the window
// when Home is next clicked by the user
exports.suppress_scroll_pointer_update = false;
exports.furthest_read = -1;
exports.server_furthest_read = -1;

var pointer_update_in_flight = false;

function update_pointer() {
    if (!pointer_update_in_flight) {
        pointer_update_in_flight = true;
        return channel.put({
            url:      '/json/users/me/pointer',
            idempotent: true,
            data:     {pointer: pointer.furthest_read},
            success: function () {
                pointer.server_furthest_read = pointer.furthest_read;
                pointer_update_in_flight = false;
            },
            error: function () {
                pointer_update_in_flight = false;
            }
        });
    } else {
        // Return an empty, resolved Deferred.
        return $.when();
    }
}


exports.send_pointer_update = function () {
    // Only bother if you've read new messages.
    if (pointer.furthest_read > pointer.server_furthest_read) {
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
    } else {
        return update_pointer();
    }
}

exports.fast_forward_pointer = function () {
    channel.get({
        url: '/users/me',
        idempotent: true,
        data: {email: page_params.email},
        success: function (data) {
            unread.mark_all_as_read(function () {
                pointer.furthest_read = data.max_message_id;
                unconditionally_send_pointer_update().then(function () {
                    ui.change_tab_to('#home');
                    reload.initiate({immediate: true,
                                     save_pointer: false,
                                     save_narrow: false,
                                     save_compose: true});
                });
            });
        }
    });
};
return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = pointer;
}
