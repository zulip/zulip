var message_flags = (function () {
var exports = {};

var batched_updaters = {};

function batched_updater(flag, op, immediate) {
    var queue = [];
    var on_success;
    var start;

    function server_request() {
        // Wait for server IDs before sending flags
        var real_msgs = _.filter(queue, function (msg) {
            return msg.local_id === undefined;
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

exports.send_starred = function send_starred(messages, value) {
    send_flag(messages, "starred", value);
};

exports.send_force_expand = function send_force_expand(messages, value) {
    send_flag(messages, "force_expand", value);
};

exports.send_force_collapse = function send_force_collapse(messages, value) {
    send_flag(messages, "force_collapse", value);
};

exports.toggle_starred = function (message) {
    if (message.flags.indexOf("starred") === -1) {
        exports.send_starred([message], true);
    } else {
        exports.send_starred([message], false);
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = message_flags;
}
