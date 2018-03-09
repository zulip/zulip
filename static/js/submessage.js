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

    // The server should sort messages for us, but this is defensive.
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
    var message_id = in_opts.message_id;
    var message = message_store.get(message_id);

    if (!message) {
        return;
    }

    var events = exports.get_message_events(message);

    if (!events) {
        return;
    }

    blueslip.info('submessages found for message id: ' + message_id);
};


exports.handle_event = function (event) {
    blueslip.info('handle submessage: ' + JSON.stringify(event));
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
