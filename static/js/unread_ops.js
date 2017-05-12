var unread_ops = (function () {

var exports = {};

exports.mark_all_as_read = function mark_all_as_read(cont) {
    _.each(message_list.all.all_messages(), function (msg) {
        msg.flags = msg.flags || [];
        msg.flags.push('read');
    });
    unread.declare_bankruptcy();
    unread_ui.update_unread_counts();

    channel.post({
        url:      '/json/messages/flags',
        idempotent: true,
        data:     {messages: JSON.stringify([]),
                   all:      true,
                   op:       'add',
                   flag:     'read'},
        success:  cont});
};

// Takes a list of messages and marks them as read
exports.mark_messages_as_read = function mark_messages_as_read(messages, options) {
    options = options || {};
    var processed = false;

    _.each(messages, function (message) {
        if (!unread.message_unread(message)) {
            // Don't do anything if the message is already read.
            return;
        }
        if (current_msg_list === message_list.narrowed) {
            unread.messages_read_in_narrow = true;
        }

        if (options.from !== "server") {
            message_flags.send_read(message);
        }

        message.flags = message.flags || [];
        message.flags.push('read');
        message.unread = false;
        unread.process_read_message(message, options);
        home_msg_list.show_message_as_read(message, options);
        message_list.all.show_message_as_read(message, options);
        if (message_list.narrowed) {
            message_list.narrowed.show_message_as_read(message, options);
        }
        notifications.close_notification(message);
        processed = true;
    });

    if (processed) {
        unread_ui.update_unread_counts();
    }
};

exports.mark_message_as_read = function mark_message_as_read(message, options) {
    exports.mark_messages_as_read([message], options);
};

// If we ever materially change the algorithm for this function, we
// may need to update notifications.received_messages as well.
exports.process_visible = function process_visible() {
    if (! notifications.window_has_focus()) {
        return;
    }

    if (feature_flags.mark_read_at_bottom) {
        if (message_viewport.bottom_message_visible()) {
            exports.mark_current_list_as_read();
        }
    } else {
        exports.mark_messages_as_read(message_viewport.visible_messages(true));
    }
};

exports.mark_current_list_as_read = function mark_current_list_as_read(options) {
    exports.mark_messages_as_read(current_msg_list.all_messages(), options);
};

exports.mark_stream_as_read = function mark_stream_as_read(stream, cont) {
    channel.post({
        url:      '/json/messages/flags',
        idempotent: true,
        data:     {messages: JSON.stringify([]),
                   all:      false,
                   op:       'add',
                   flag:     'read',
                   stream_name: stream,
                  },
        success:  cont});
};

exports.mark_topic_as_read = function mark_topic_as_read(stream, topic, cont) {
    channel.post({
    url:      '/json/messages/flags',
    idempotent: true,
    data:     {messages: JSON.stringify([]),
               all:      false,
               op:       'add',
               flag:     'read',
               topic_name: topic,
               stream_name: stream,
               },
    success:  cont});
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread_ops;
}
