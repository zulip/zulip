var sent_messages = (function () {

var exports = {};

exports.send_times_log = [];
exports.send_times_data = {};

function report_send_time(send_time, receive_time, display_time, locally_echoed, rendered_changed) {
    var data = {time: send_time.toString(),
                received: receive_time.toString(),
                displayed: display_time.toString(),
                locally_echoed: locally_echoed};
    if (locally_echoed) {
        data.rendered_content_disparity = rendered_changed;
    }
    channel.post({
        url: '/json/report_send_time',
        data: data,
    });
}

function maybe_report_send_times(message_id) {
    var data = exports.send_times_data[message_id];
    if (data.send_finished === undefined || data.received === undefined ||
        data.displayed === undefined) {
        // We report the data once we have both the send and receive times
        return;
    }
    report_send_time(data.send_finished - data.start,
                     data.received - data.start,
                     data.displayed - data.start,
                     data.locally_echoed,
                     data.rendered_content_disparity || false);
}

function mark_end_to_end_receive_time(message_id) {
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = {};
    }
    exports.send_times_data[message_id].received = new Date();
    maybe_report_send_times(message_id);
}

function mark_end_to_end_display_time(message_id) {
    exports.send_times_data[message_id].displayed = new Date();
    maybe_report_send_times(message_id);
}

exports.mark_rendered_content_disparity = function (message_id, changed) {
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = {};
    }
    exports.send_times_data[message_id].rendered_content_disparity = changed;
};

exports.report_as_received = function report_as_received(message) {
    if (message.sent_by_me) {
        mark_end_to_end_receive_time(message.id);
        setTimeout(function () {
            mark_end_to_end_display_time(message.id);
        }, 0);
    }
};

exports.process_success = function (message_id, start_time, locally_echoed) {
    var send_finished = new Date();
    var send_time = (send_finished - start_time);
    if (feature_flags.log_send_times) {
        blueslip.log("send time: " + send_time);
    }
    if (feature_flags.collect_send_times) {
        exports.send_times_log.push(send_time);
    }
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = {};
    }
    exports.send_times_data[message_id].start = start_time;
    exports.send_times_data[message_id].send_finished = send_finished;
    exports.send_times_data[message_id].locally_echoed  = locally_echoed;
    maybe_report_send_times(message_id);
};

exports.set_timer_for_restarting_event_loop = function (message_id) {
    setTimeout(function () {
        if (exports.send_times_data[message_id].received === undefined) {
            blueslip.log("Restarting get_events due to delayed receipt of sent message " + message_id);
            server_events.restart_get_events();
        }
    }, 5000);
};

exports.clear = function (message_id) {
    delete exports.send_times_data[message_id];
};

exports.initialize = function () {
    $(document).on('message_id_changed', function (event) {
        if (exports.send_times_data[event.old_id] !== undefined) {
            var value = exports.send_times_data[event.old_id];
            delete exports.send_times_data[event.old_id];
            exports.send_times_data[event.new_id] =
                _.extend({}, exports.send_times_data[event.old_id], value);
        }
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = sent_messages;
}
