import _ from "lodash";

import * as channel from "./channel";
import * as message_store from "./message_store";
import * as starred_messages from "./starred_messages";
import * as ui from "./ui";
import * as unread_ops from "./unread_ops";

function send_flag_update_for_messages(msg_ids, flag, op) {
    channel.post({
        url: "/json/messages/flags",
        idempotent: true,
        data: {
            messages: JSON.stringify(msg_ids),
            flag,
            op,
        },
    });
}
export const _unread_batch_size = 1000;

export const send_read = (function () {
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

        const real_msg_ids_batch = real_msg_ids.slice(0, _unread_batch_size);

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

export function save_collapsed(message) {
    send_flag_update_for_messages([message.id], "collapsed", "add");
}

export function save_uncollapsed(message) {
    send_flag_update_for_messages([message.id], "collapsed", "remove");
}

// This updates the state of the starred flag in local data
// structures, and triggers a UI rerender.
export function update_starred_flag(message_id, new_value) {
    const message = message_store.get(message_id);
    if (message === undefined) {
        // If we don't have the message locally, do nothing; if later
        // we fetch it, it'll come with the correct `starred` state.
        return;
    }
    message.starred = new_value;
    ui.update_starred_view(message_id, new_value);
}

export function toggle_starred_and_update_server(message) {
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
        send_flag_update_for_messages([message.id], "starred", "add");
        starred_messages.add([message.id]);
    } else {
        send_flag_update_for_messages([message.id], "starred", "remove");
        starred_messages.remove([message.id]);
    }
}

export function unstar_all_messages() {
    const starred_msg_ids = starred_messages.get_starred_msg_ids();
    send_flag_update_for_messages(starred_msg_ids, "starred", "remove");
}

export function unstar_all_messages_in_topic(stream_id, topic) {
    const data = {
        anchor: "newest",
        // In the unlikely event the user has >1000 starred messages
        // in a topic, this won't find them all. This is probably an
        // acceptable bug; one can do it multiple times, and we avoid
        // creating an API endpoint just for this very minor feature.
        num_before: 1000,
        num_after: 0,
        narrow: JSON.stringify([
            {operator: "stream", operand: stream_id},
            {operator: "topic", operand: topic},
            {operator: "is", operand: "starred"},
        ]),
    };

    channel.get({
        url: "/json/messages",
        data,
        idempotent: true,
        success(data) {
            const messages = data.messages;
            const starred_message_ids = messages.map((message) => message.id);
            send_flag_update_for_messages(starred_message_ids, "starred", "remove");
        },
    });
}
