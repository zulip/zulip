var sent_messages = (function () {

var exports = {};

exports.send_times_log = [];
exports.send_times_data = {};

exports.reset_id_state = function () {
    exports.local_id_dict = new Dict();
    exports.next_client_message_id = 0;
};

exports.get_new_client_message_id = function (opts) {
    exports.next_client_message_id += 1;
    var client_message_id = exports.next_client_message_id;
    exports.local_id_dict.set(client_message_id, opts.local_id);
    return client_message_id;
};

exports.get_local_id = function (opts) {
    var client_message_id = opts.client_message_id;

    if (client_message_id === undefined) {
        return undefined;
    }

    return exports.local_id_dict.get(client_message_id);
};

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

exports.track_message = function (opts) {
    var client_message_id = opts.client_message_id;

    if (exports.send_times_data[client_message_id] !== undefined) {
        blueslip.error('We are re-using a client_message_id');
        return;
    }

    var state = exports.message_state(opts);

    exports.send_times_data[client_message_id] = state;

    return state;
};

exports.message_state = function (opts) {
    var self = {};
    self.data = {};

    self.data.start = new Date();

    self.data.client_message_id = opts.client_message_id;
    self.data.locally_echoed = opts.locally_echoed;


    self.data.received = undefined;
    self.data.displayed = undefined;
    self.data.send_finished = undefined;
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

    self.process_success = function () {
        var send_finished = new Date();

        var send_time = (send_finished - self.data.start);
        if (feature_flags.log_send_times) {
            blueslip.log("send time: " + send_time);
        }
        if (feature_flags.collect_send_times) {
            exports.send_times_log.push(send_time);
        }

        self.data.send_finished = send_finished;
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

exports.get_message_state = function (client_message_id) {
    var state = exports.send_times_data[client_message_id];

    if (!state) {
        blueslip.warn('Unknown client_message_id' + client_message_id);
    }

    return state;
};


function mark_end_to_end_receive_time(client_message_id) {
    var state = exports.get_message_state(client_message_id);
    if (!state) {
        return;
    }
    state.mark_received();
}

function mark_end_to_end_display_time(client_message_id) {
    var state = exports.get_message_state(client_message_id);
    if (!state) {
        return;
    }
    state.mark_displayed();
}

exports.mark_rendered_content_disparity = function (opts) {
    var state = exports.get_message_state(opts.client_message_id);
    if (!state) {
        return;
    }
    state.mark_disparity(opts.changed);
};

exports.report_as_received = function report_as_received(client_message_id) {
    if (client_message_id) {
        mark_end_to_end_receive_time(client_message_id);
        setTimeout(function () {
            mark_end_to_end_display_time(client_message_id);
        }, 0);
    }
};

exports.set_timer_for_restarting_event_loop = function (client_message_id) {
    setTimeout(function () {
        if (!exports.send_times_data[client_message_id].was_received()) {
            blueslip.log("Restarting get_events due to delayed receipt of sent message " + client_message_id);
            server_events.restart_get_events();
        }
    }, 5000);
};

exports.initialize = function () {
    exports.reset_id_state();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = sent_messages;
}
