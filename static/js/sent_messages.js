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

exports.message_state = function () {
    var self = {};
    self.data = {};

    // TODO: Fix quirk that we don't know the start time sometime
    //       when we start recording message state.
    self.data.start = undefined;
    self.data.received = undefined;
    self.data.displayed = undefined;
    self.data.send_finished = undefined;
    self.data.locally_echoed = false;
    self.data.rendered_content_disparity = false;

    self.maybe_report_send_times = function () {
        if (!self.ready()) {
            return;
        }
        var data = self.data;
        report_send_time(data.send_finished - data.start,
                         data.received - data.start,
                         data.displayed - data.start,
                         data.locally_echoed,
                         data.rendered_content_disparity || false);
    };

    self.mark_received = function () {
        self.data.received = new Date();
        self.maybe_report_send_times();
    };

    self.mark_displayed = function () {
        self.data.displayed = new Date();
        self.maybe_report_send_times();
    };

    self.mark_disparity = function (changed) {
        self.data.rendered_content_disparity = changed;
    };

    self.process_success = function (opts) {
        self.data.start = opts.start;
        self.data.send_finished = opts.send_finished;
        self.data.locally_echoed = opts.locally_echoed;
        self.maybe_report_send_times();
    };

    self.was_received = function () {
        return self.data.received !== undefined;
    };

    self.ready = function () {
        return (self.data.send_finished !== undefined) &&
               (self.data.received !== undefined) &&
               (self.data.displayed !== undefined);
    };

    return self;
};

exports.get_message_state = function (message_id) {
    if (exports.send_times_data[message_id] === undefined) {
        exports.send_times_data[message_id] = exports.message_state();
    }

    return exports.send_times_data[message_id];
};


function mark_end_to_end_receive_time(message_id) {
    var state = exports.get_message_state(message_id);
    state.mark_received();
}

function mark_end_to_end_display_time(message_id) {
    var state = exports.get_message_state(message_id);
    state.mark_displayed();
}

exports.mark_rendered_content_disparity = function (message_id, changed) {
    var state = exports.get_message_state(message_id);
    state.mark_disparity(changed);
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

    var state = exports.get_message_state(message_id);
    state.process_success({
        start: start_time,
        send_finished: send_finished,
        locally_echoed: locally_echoed,
    });
};

exports.set_timer_for_restarting_event_loop = function (message_id) {
    setTimeout(function () {
        if (!exports.send_times_data[message_id].was_received()) {
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
            exports.send_times_data[event.new_id] = value;
            delete exports.send_times_data[event.old_id];
        }
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = sent_messages;
}
