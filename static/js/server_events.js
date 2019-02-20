var server_events = (function () {
// Docs: https://zulip.readthedocs.io/en/latest/subsystems/events-system.html

var exports = {};

var waiting_on_homeview_load = true;

var events_stored_while_loading = [];

var get_events_xhr;
var get_events_timeout;
var get_events_failures = 0;
var get_events_params = {};

// This field keeps track of whether we are attempting to
// force-reconnect to the events server due to suspecting we are
// offline.  It is important for avoiding races with the presence
// system when coming back from unsuspend.
exports.suspect_offline = false;

function get_events_success(events) {
    var messages = [];
    var update_message_events = [];
    var post_message_events = [];
    var new_pointer;

    var clean_event = function clean_event(event) {
        // Only log a whitelist of the event to remove private data
        return _.pick(event, 'id', 'type', 'op');
    };

    _.each(events, function (event) {
        try {
            get_events_params.last_event_id = Math.max(get_events_params.last_event_id,
                                                       event.id);
        } catch (ex) {
            blueslip.error('Failed to update last_event_id',
                           {event: clean_event(event)},
                           ex.stack);
        }
    });

    if (waiting_on_homeview_load) {
        events_stored_while_loading = events_stored_while_loading.concat(events);
        return;
    }

    if (events_stored_while_loading.length > 0) {
        events = events_stored_while_loading.concat(events);
        events_stored_while_loading = [];
    }

    // Most events are dispatched via the code server_events_dispatch,
    // called in the default case.  The goal of this split is to avoid
    // contributors needing to read or understand the complex and
    // rarely modified logic for non-normal events.
    var dispatch_event = function dispatch_event(event) {
        switch (event.type) {
        case 'message':
            var msg = event.message;
            msg.flags = event.flags;
            if (event.local_message_id) {
                msg.local_id = event.local_message_id;
                sent_messages.report_event_received(event.local_message_id);
            }
            messages.push(msg);
            break;

        case 'pointer':
            new_pointer = event.pointer;
            break;

        case 'update_message':
            update_message_events.push(event);
            break;

        case 'delete_message':
        case 'submessage':
        case 'update_message_flags':
            post_message_events.push(event);
            break;

        default:
            return server_events_dispatch.dispatch_normal_event(event);
        }
    };

    _.each(events, function (event) {
        try {
            dispatch_event(event);
        } catch (ex1) {
            blueslip.error('Failed to process an event\n' +
                           blueslip.exception_msg(ex1),
                           {event: clean_event(event)},
                           ex1.stack);
        }
    });

    if (messages.length !== 0) {
        // Sort by ID, so that if we get multiple messages back from
        // the server out-of-order, we'll still end up with our
        // message lists in order.
        messages = _.sortBy(messages, 'id');
        try {
            messages = echo.process_from_server(messages);
            if (messages.length > 0) {
                _.each(messages, message_store.set_message_booleans);
                var sent_by_this_client = false;
                _.each(messages, function (msg) {
                    var msg_state = sent_messages.messages[msg.local_id];
                    if (msg_state) {
                        // Almost every time, this message will be the
                        // only one in messages, because multiple messages
                        // being returned by get_events usually only
                        // happens when a client is offline, but we know
                        // this client just sent a message in this batch
                        // of events.  But in any case,
                        // insert_new_messages handles multiple messages,
                        // only one of which was sent by this client,
                        // correctly.
                        sent_by_this_client = true;
                    }
                });
                message_events.insert_new_messages(messages, sent_by_this_client);
            }
        } catch (ex2) {
            blueslip.error('Failed to insert new messages\n' +
                           blueslip.exception_msg(ex2),
                           undefined,
                           ex2.stack);
        }
    }

    if (new_pointer !== undefined
        && new_pointer > pointer.furthest_read) {
        pointer.furthest_read = new_pointer;
        pointer.server_furthest_read = new_pointer;
        home_msg_list.select_id(new_pointer, {then_scroll: true, use_closest: true});
    }

    if (home_msg_list.selected_id() === -1 && !home_msg_list.empty()) {
        home_msg_list.select_id(home_msg_list.first().id, {then_scroll: false});
    }

    if (update_message_events.length !== 0) {
        try {
            message_events.update_messages(update_message_events);
        } catch (ex3) {
            blueslip.error('Failed to update messages\n' +
                           blueslip.exception_msg(ex3),
                           undefined,
                           ex3.stack);
        }
    }

    // We do things like updating message flags and deleting messages last,
    // to avoid ordering issues that are caused by batch handling of
    // messages above.
    _.each(post_message_events, function (event) {
        server_events_dispatch.dispatch_normal_event(event);
    });
}

function show_ui_connection_error() {
    ui_report.show_error($("#connection-error"));
    $("#connection-error").addClass('get-events-error');
}

function hide_ui_connection_error() {
    ui_report.hide_error($("#connection-error"));
    $("#connection-error").removeClass('get-events-error');
}

function get_events(options) {
    options = _.extend({dont_block: false}, options);

    if (reload_state.is_in_progress()) {
        return;
    }

    get_events_params.dont_block = options.dont_block || get_events_failures > 0;

    if (get_events_params.dont_block) {
        // If we're requesting an immediate re-connect to the server,
        // that means it's fairly likely that this client has been off
        // the Internet and thus may have stale state (which is
        // important for potential presence issues).
        exports.suspect_offline = true;
    }
    if (get_events_params.queue_id === undefined) {
        get_events_params.queue_id = page_params.queue_id;
        get_events_params.last_event_id = page_params.last_event_id;
    }

    if (get_events_xhr !== undefined) {
        get_events_xhr.abort();
    }
    if (get_events_timeout !== undefined) {
        clearTimeout(get_events_timeout);
    }

    get_events_params.client_gravatar = true;

    get_events_timeout = undefined;
    get_events_xhr = channel.get({
        url: '/json/events',
        data: get_events_params,
        idempotent: true,
        timeout: page_params.poll_timeout,
        success: function (data) {
            exports.suspect_offline = false;
            try {
                get_events_xhr = undefined;
                get_events_failures = 0;
                hide_ui_connection_error();

                get_events_success(data.events);
            } catch (ex) {
                blueslip.error('Failed to handle get_events success\n' +
                               blueslip.exception_msg(ex),
                               undefined,
                               ex.stack);
            }
            get_events_timeout = setTimeout(get_events, 0);
        },
        error: function (xhr, error_type) {
            try {
                get_events_xhr = undefined;
                // If we're old enough that our message queue has been
                // garbage collected, immediately reload.
                if (xhr.status === 400 &&
                    JSON.parse(xhr.responseText).code === 'BAD_EVENT_QUEUE_ID') {
                    page_params.event_queue_expired = true;
                    reload.initiate({immediate: true,
                                     save_pointer: false,
                                     save_narrow: true,
                                     save_compose: true});
                }

                if (error_type === 'abort') {
                    // Don't restart if we explicitly aborted
                    return;
                } else if (error_type === 'timeout') {
                    // Retry indefinitely on timeout.
                    get_events_failures = 0;
                    hide_ui_connection_error();
                } else {
                    get_events_failures += 1;
                }

                if (get_events_failures >= 5) {
                    show_ui_connection_error();
                } else {
                    hide_ui_connection_error();
                }
            } catch (ex) {
                blueslip.error('Failed to handle get_events error\n' +
                               blueslip.exception_msg(ex),
                               undefined,
                               ex.stack);
            }
            var retry_sec = Math.min(90, Math.exp(get_events_failures / 2));
            get_events_timeout = setTimeout(get_events, retry_sec * 1000);
        },
    });
}

exports.assert_get_events_running = function assert_get_events_running(error_message) {
    if (get_events_xhr === undefined && get_events_timeout === undefined) {
        exports.restart_get_events({dont_block: true});
        blueslip.error(error_message);
    }
};

exports.restart_get_events = function restart_get_events(options) {
    get_events(options);
};

exports.force_get_events = function force_get_events() {
    get_events_timeout = setTimeout(get_events, 0);
};

exports.home_view_loaded = function home_view_loaded() {
    waiting_on_homeview_load = false;
    get_events_success([]);
    $(document).trigger("home_view_loaded.zulip");
};


var watchdog_time = $.now();
exports.check_for_unsuspend = function () {
    var new_time = $.now();
    if (new_time - watchdog_time > 20000) { // 20 seconds.
        // Defensively reset watchdog_time here in case there's an
        // exception in one of the event handlers
        watchdog_time = new_time;
        // Our app's JS wasn't running, which probably means the machine was
        // asleep.
        $(document).trigger($.Event('unsuspend'));
    }
    watchdog_time = new_time;
};
setInterval(exports.check_for_unsuspend, 5000);

exports.initialize = function () {
    $(document).on('unsuspend', function () {
        // Immediately poll for new events on unsuspend
        blueslip.log("Restarting get_events due to unsuspend");
        get_events_failures = 0;
        exports.restart_get_events({dont_block: true});
    });
    get_events();
};

exports.cleanup_event_queue = function cleanup_event_queue() {
    // Submit a request to the server to cleanup our event queue
    if (page_params.event_queue_expired === true) {
        return;
    }
    blueslip.log("Cleaning up our event queue");
    // Set expired because in a reload we may be called twice.
    page_params.event_queue_expired = true;
    channel.del({
        url: '/json/events',
        data: {queue_id: page_params.queue_id},
    });
};

window.addEventListener("beforeunload", function () {
    exports.cleanup_event_queue();
});

// For unit testing
exports._get_events_success = get_events_success;

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = server_events;
}
window.server_events = server_events;
