"use strict";

exports.mark_all_as_read = function () {
    unread.declare_bankruptcy();
    unread_ui.update_unread_counts();

    channel.post({
        url: "/json/mark_all_as_read",
        idempotent: true,
        success: () => {
            // After marking all messages as read, we reload the browser.
            // This is useful to avoid leaving ourselves deep in the past.
            reload.initiate({
                immediate: true,
                save_pointer: false,
                save_narrow: true,
                save_compose: true,
            });
        },
    });
};

function process_newly_read_message(message, options) {
    home_msg_list.show_message_as_read(message, options);
    message_list.all.show_message_as_read(message, options);
    if (message_list.narrowed) {
        message_list.narrowed.show_message_as_read(message, options);
    }
    notifications.close_notification(message);
    recent_topics.update_topic_unread_count(message);
}

exports.process_read_messages_event = function (message_ids) {
    /*
        This code has a lot in common with notify_server_messages_read,
        but there are subtle differences due to the fact that the
        server can tell us about unread messages that we didn't
        actually read locally (and which we may not have even
        loaded locally).
    */
    const options = {from: "server"};

    message_ids = unread.get_unread_message_ids(message_ids);
    if (message_ids.length === 0) {
        return;
    }

    for (const message_id of message_ids) {
        if (current_msg_list === message_list.narrowed) {
            // I'm not sure this entirely makes sense for all server
            // notifications.
            unread.set_messages_read_in_narrow(true);
        }

        unread.mark_as_read(message_id);

        const message = message_store.get(message_id);

        if (message) {
            process_newly_read_message(message, options);
        }
    }

    unread_ui.update_unread_counts();
};

// Takes a list of messages and marks them as read.
// Skips any messages that are already marked as read.
exports.notify_server_messages_read = function (messages, options) {
    options = options || {};
    messages = unread.get_unread_messages(messages);
    if (messages.length === 0) {
        return;
    }

    message_flags.send_read(messages);

    for (const message of messages) {
        if (current_msg_list === message_list.narrowed) {
            unread.set_messages_read_in_narrow(true);
        }

        unread.mark_as_read(message.id);
        process_newly_read_message(message, options);
    }

    unread_ui.update_unread_counts();
};

exports.notify_server_message_read = function (message, options) {
    exports.notify_server_messages_read([message], options);
};

// If we ever materially change the algorithm for this function, we
// may need to update notifications.received_messages as well.
exports.process_visible = function () {
    if (overlays.is_active() || !notifications.is_window_focused()) {
        return;
    }

    if (message_viewport.bottom_message_visible() && current_msg_list.can_mark_messages_read()) {
        exports.mark_current_list_as_read();
    }
};

exports.mark_current_list_as_read = function (options) {
    exports.notify_server_messages_read(current_msg_list.all_messages(), options);
};

exports.mark_stream_as_read = function (stream_id, cont) {
    channel.post({
        url: "/json/mark_stream_as_read",
        idempotent: true,
        data: {stream_id},
        success: cont,
    });
};

exports.mark_topic_as_read = function (stream_id, topic, cont) {
    channel.post({
        url: "/json/mark_topic_as_read",
        idempotent: true,
        data: {stream_id, topic_name: topic},
        success: cont,
    });
};

window.unread_ops = exports;
