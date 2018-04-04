var message_flags = (function () {
var exports = {};

function send_flag_update(message, flag, op) {
    channel.post({
        url: '/json/messages/flags',
        idempotent: true,
        data: {
            messages: JSON.stringify([message.id]),
            flag: flag,
            op: op,
        },
    });
}

exports.send_read = (function () {
    var queue = [];
    var on_success;
    var start;

    function server_request() {
        // Wait for server IDs before sending flags
        var real_msgs = _.filter(queue, function (msg) {
            return !msg.locally_echoed;
        });
        var real_msg_ids = _.map(real_msgs, function (msg) {
            return msg.id;
        });

        if (real_msg_ids.length === 0) {
            setTimeout(start, 100);
            return;
        }

        // We have some real IDs.  If there are any left in the queue when this
        // call finishes, they will be handled in the success callback.

        channel.post({
            url:      '/json/messages/flags',
            idempotent: true,
            data:     {messages: JSON.stringify(real_msg_ids),
                       op:       'add',
                       flag:     'read'},
            success:  on_success,
        });
    }

    start = _.throttle(server_request, 1000);

    on_success = function on_success(data) {
        if (data ===  undefined || data.messages === undefined) {
            return;
        }

        queue = _.filter(queue, function (message) {
            return data.messages.indexOf(message.id) === -1;
        });

        if (queue.length > 0) {
            start();
        }
    };

    function add(messages) {
        queue = queue.concat(messages);
        start();
    }

    return add;
}());

exports.save_collapsed = function (message) {
    send_flag_update(message, 'collapsed', true);
};

exports.save_uncollapsed = function (message) {
    send_flag_update(message, 'collapsed', true);
};

exports.toggle_starred = function (message) {
    if (message.locally_echoed) {
        // This is defensive code for when you hit the "*" key
        // before we get a server ack.  It's rare that somebody
        // can star this quickly, and we don't have a good way
        // to tell the server which message was starred.
        return;
    }

    message.starred = !message.starred;

    unread_ops.notify_server_message_read(message);
    ui.update_starred(message);

    if (message.starred) {
        send_flag_update(message, 'starred', 'add');
    } else {
        send_flag_update(message, 'starred', 'remove');
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = message_flags;
}
