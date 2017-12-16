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

var batched_updaters = {};

function batched_updater(flag, op, immediate) {
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
                       op:       op,
                       flag:     flag},
            success:  on_success,
        });
    }

    if (immediate) {
        start = server_request;
    } else {
        start = _.debounce(server_request, 1000);
    }

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

    function add(message) {
        if (message.flags === undefined) {
            message.flags = [];
        }
        if (op === 'add')  {
            message.flags.push(flag);
        } else {
            message.flags = _.without(message.flags, flag);
        }
        queue.push(message);
        start();
    }

    return add;
}

exports.send_read = batched_updater('read', 'add');

function send_flag(messages, flag_name, set_flag) {
    var op = set_flag ? 'add' : 'remove';
    var flag_key = flag_name + '_' + op;
    var updater;

    if (batched_updaters.hasOwnProperty(flag_key)) {
        updater = batched_updaters[flag_key];
    } else {
        updater = batched_updater(flag_name, op, true);
        batched_updaters[flag_key] = updater;
    }

    _.each(messages, function (message) {
        updater(message);
    });
}

exports.send_collapsed = function send_collapse(messages, value) {
    send_flag(messages, "collapsed", value);
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

    unread_ops.mark_message_as_read(message);
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
