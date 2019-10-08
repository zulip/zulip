var submessage = (function () {

var exports = {};

exports.get_message_events = function (message) {
    if (message.locally_echoed) {
        return;
    }

    if (!message.submessages) {
        return;
    }

    if (message.submessages.length === 0) {
        return;
    }

    message.submessages.sort(function (m1, m2) {
        return parseInt(m1.id, 10) - parseInt(m2.id, 10);
    });

    var events = _.map(message.submessages, function (obj) {
        return {
            sender_id: obj.sender_id,
            data: JSON.parse(obj.content),
        };
    });

    return events;
};

exports.process_submessages = function (in_opts) {
    // This happens in our rendering path, so we try to limit any
    // damage that may be triggered by one rogue message.
    try {
        return exports.do_process_submessages(in_opts);
    } catch (err) {
        blueslip.error('in process_submessages: ' + err.message);
    }
};

exports.do_process_submessages = function (in_opts) {
    var message_id = in_opts.message_id;
    var message = message_store.get(message_id);

    if (!message) {
        return;
    }

    var events = exports.get_message_events(message);

    if (!events) {
        return;
    }

    var row = in_opts.row;

    // Right now, our only use of submessages is widgets.

    var data = events[0].data;

    if (data === undefined) {
        return;
    }

    var widget_type = data.widget_type;

    if (widget_type === undefined) {
        return;
    }

    var post_to_server = exports.make_server_callback(message_id);

    widgetize.activate({
        widget_type: widget_type,
        extra_data: data.extra_data,
        events: events,
        row: row,
        message: message,
        post_to_server: post_to_server,
    });
};

exports.update_message = function (submsg) {
    var message = message_store.get(submsg.message_id);

    if (message === undefined) {
        // This is generally not a problem--the server
        // can send us events without us having received
        // the original message, since the server doesn't
        // track that.
        return;
    }

    var existing = _.find(message.submessages, function (sm) {
        return sm.id === submsg.id;
    });

    if (existing !== undefined) {
        blueslip.warn("Got submessage multiple times: " + submsg.id);
        return;
    }

    if (message.submessages === undefined) {
        message.submessages = [];
    }

    message.submessages.push(submsg);
};

exports.handle_event = function (submsg) {
    // Update message.submessages in case we haven't actually
    // activated the widget yet, so that when the message does
    // come in view, the data will be complete.
    exports.update_message(submsg);

    // Right now, our only use of submessages is widgets.
    var msg_type = submsg.msg_type;

    if (msg_type !== 'widget') {
        blueslip.warn('unknown msg_type: ' + msg_type);
        return;
    }

    var data;

    try {
        data = JSON.parse(submsg.content);
    } catch (err) {
        blueslip.error('server sent us invalid json in handle_event: ' + submsg.content);
        return;
    }

    widgetize.handle_event({
        sender_id: submsg.sender_id,
        message_id: submsg.message_id,
        data: data,
    });
};

exports.make_server_callback = function (message_id) {
    return function (opts) {
        var url = '/json/submessage';

        channel.post({
            url: url,
            data: {
                message_id: message_id,
                msg_type: opts.msg_type,
                content: JSON.stringify(opts.data),
            },
        });
    };
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = submessage;
}

window.submessage = submessage;
