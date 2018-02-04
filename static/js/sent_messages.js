var sent_messages = (function () {

var exports = {};

exports.messages = {};

exports.reset_id_state = function () {
    exports.next_local_id = 0;
};

exports.get_new_local_id = function () {
    exports.next_local_id += 1;
    var local_id = exports.next_local_id;
    return 'loc-' + local_id.toString();
};

function report_send_time(send_time, receive_time,
                          locally_echoed, rendered_changed) {
    var data = {
        time: send_time.toString(),
        received: receive_time.toString(),
        locally_echoed: locally_echoed,
    };

    if (locally_echoed) {
        data.rendered_content_disparity = rendered_changed;
    }

    channel.post({
        url: '/json/report/send_times',
        data: data,
    });
}

exports.start_tracking_message = function (opts) {
    var local_id = opts.local_id;

    if (!opts.local_id) {
        blueslip.error('You must supply a local_id');
        return;
    }

    if (exports.messages[local_id] !== undefined) {
        blueslip.error('We are re-using a local_id');
        return;
    }

    var state = exports.message_state(opts);

    exports.messages[local_id] = state;
};

exports.message_state = function (opts) {
    var self = {};
    self.data = {};

    self.data.start = new Date();

    self.data.local_id = opts.local_id;
    self.data.locally_echoed = opts.locally_echoed;


    self.data.received = undefined;
    self.data.send_finished = undefined;
    self.data.rendered_content_disparity = false;

    self.start_resend = function () {
        self.data.start = new Date();
        self.data.received = undefined;
        self.data.send_finished = undefined;
        self.data.rendered_content_disparity = false;
    };

    self.maybe_restart_event_loop = function () {
        if (self.data.received) {
            // We got our event, no need to do anything
            return;
        }

        blueslip.log("Restarting get_events due to " +
                     "delayed receipt of sent message " +
                     self.data.local_id);

        server_events.restart_get_events();
    };

    self.maybe_report_send_times = function () {
        if (!self.ready()) {
            return;
        }
        var data = self.data;
        report_send_time(data.send_finished - data.start,
                         data.received - data.start,
                         data.locally_echoed,
                         data.rendered_content_disparity);
    };

    self.report_event_received = function () {
        self.data.received = new Date();
        self.maybe_report_send_times();
    };

    self.mark_disparity = function () {
        self.data.rendered_content_disparity = true;
    };

    self.report_server_ack = function () {
        self.data.send_finished = new Date();
        self.maybe_report_send_times();

        // We only start our timer for events coming in here,
        // since it's plausible the server rejected our message,
        // or took a while to process it, but there is nothing
        // wrong with our event loop.

        if (!self.data.received) {
            setTimeout(self.maybe_restart_event_loop, 5000);
        }
    };

    self.ready = function () {
        return (self.data.send_finished !== undefined) &&
               (self.data.received !== undefined);
    };

    return self;
};

exports.get_message_state = function (local_id) {
    var state = exports.messages[local_id];

    if (!state) {
        blueslip.warn('Unknown local_id: ' + local_id);
    }

    return state;
};


exports.mark_disparity = function (local_id) {
    var state = exports.get_message_state(local_id);
    if (!state) {
        return;
    }
    state.mark_disparity();
};

exports.report_event_received = function (local_id) {
    var state = exports.get_message_state(local_id);
    if (!state) {
        return;
    }

    state.report_event_received();
};

exports.start_resend = function (local_id) {
    var state = exports.get_message_state(local_id);
    if (!state) {
        return;
    }

    state.start_resend();
};

exports.report_server_ack = function (local_id) {
    var state = exports.get_message_state(local_id);
    if (!state) {
        return;
    }

    state.report_server_ack();
};

exports.initialize = function () {
    exports.reset_id_state();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = sent_messages;
}
