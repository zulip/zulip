"use strict";

const _ = require("lodash");

function send_flag_update(message, flag, op) {
    channel.post({
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: JSON.stringify([message.id]),
            flag,
            op,
        },
    });
}
exports._unread_batch_size = 1000;
exports.send_read = (function () {
    let queue = [];
    let on_success;
    let start;
    function server_request() {
        // Wait for server IDs before sending flags
        const real_msgs = queue.filter((msg) => !msg.locally_echoed);
        const real_msg_ids = real_msgs.map((msg) => msg.id);

        if (real_msg_ids.length === 0) {
            setTimeout(start, 100);
            return;
        }

        const real_msg_ids_batch = real_msg_ids.slice(0, exports._unread_batch_size);

        // We have some real IDs.  If there are any left in the queue when this
        // call finishes, they will be handled in the success callback.

        channel.post({
            url: "/json/messages/flags",
            idempotent: true,
            data: {messages: JSON.stringify(real_msg_ids_batch), op: "add", flag: "read"},
            success: on_success,
        });
    }

    start = _.throttle(server_request, 1000);

    on_success = function on_success(data) {
        if (data === undefined || data.messages === undefined) {
            return;
        }

        queue = queue.filter((message) => !data.messages.includes(message.id));

        if (queue.length > 0) {
            start();
        }
    };

    function add(messages) {
        queue = queue.concat(messages);
        start();
    }

    return add;
})();

exports.save_collapsed = function (message) {
    send_flag_update(message, "collapsed", "add");
};

exports.save_uncollapsed = function (message) {
    send_flag_update(message, "collapsed", "remove");
};

// This updates the state of the starred flag in local data
// structures, and triggers a UI rerender.
exports.update_starred_flag = function (message_id, new_value) {
    const message = message_store.get(message_id);
    if (message === undefined) {
        // If we don't have the message locally, do nothing; if later
        // we fetch it, it'll come with the correct `starred` state.
        return;
    }
    message.starred = new_value;
    ui.update_starred_view(message_id, new_value);
};

exports.toggle_starred_and_update_server = function (message) {
    if (message.locally_echoed) {
        // This is defensive code for when you hit the "*" key
        // before we get a server ack.  It's rare that somebody
        // can star this quickly, and we don't have a good way
        // to tell the server which message was starred.
        return;
    }

    message.starred = !message.starred;

    // Unlike most calls to mark messages as read, we don't check
    // msg_list.can_mark_messages_read, because starring a message is an
    // explicit interaction and we'd like to preserve the user
    // expectation invariant that all starred messages are read.
    unread_ops.notify_server_message_read(message);
    ui.update_starred_view(message.id, message.starred);

    if (message.starred) {
        send_flag_update(message, "starred", "add");
        starred_messages.add([message.id]);
    } else {
        send_flag_update(message, "starred", "remove");
        starred_messages.remove([message.id]);
    }
};

exports.unstar_all_messages = function () {
    const starred_msg_ids = starred_messages.get_starred_msg_ids();
    channel.post({
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: JSON.stringify(starred_msg_ids),
            flag: "starred",
            op: "remove",
        },
    });
};

window.message_flags = exports;
