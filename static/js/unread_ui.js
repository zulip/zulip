var unread_ui = (function () {

var exports = {};

var last_private_message_count = 0;
var last_mention_count = 0;

function do_new_messages_animation(li) {
    li.addClass("new_messages");
    function mid_animation() {
        li.removeClass("new_messages");
        li.addClass("new_messages_fadeout");
    }
    function end_animation() {
        li.removeClass("new_messages_fadeout");
    }
    setTimeout(mid_animation, 3000);
    setTimeout(end_animation, 6000);
}

exports.animate_private_message_changes = function (li, new_private_message_count) {
    if (new_private_message_count > last_private_message_count) {
        do_new_messages_animation(li);
    }
    last_private_message_count = new_private_message_count;
};

exports.animate_mention_changes = function (li, new_mention_count) {
    if (new_mention_count > last_mention_count) {
        do_new_messages_animation(li);
    }
    last_mention_count = new_mention_count;
};

exports.set_count_toggle_button = function (elem, count) {
    if (count === 0) {
        if (elem.is(':animated')) {
            return elem.stop(true, true).hide();
        }
        return elem.hide(500);
    } else if ((count > 0) && (count < 1000)) {
        elem.show(500);
        return elem.text(count);
    }
    elem.show(500);
    return elem.text("1k+");
};

exports.update_unread_counts = function () {
    if (unread.suppress_unread_counts) {
        return;
    }

    // Pure computation:
    var res = unread.get_counts();

    // Side effects from here down:
    // This updates some DOM elements directly, so try to
    // avoid excessive calls to this.
    activity.update_dom_with_unread_counts(res);
    stream_list.update_dom_with_unread_counts(res);
    pm_list.update_dom_with_unread_counts(res);
    notifications.update_title_count(res.home_unread_messages);
    notifications.update_pm_count(res.private_message_count);
};

exports.enable = function enable() {
    unread.suppress_unread_counts = false;
    exports.update_unread_counts();
};

exports.mark_all_as_read = function mark_all_as_read(cont) {
    _.each(message_list.all.all_messages(), function (msg) {
        msg.flags = msg.flags || [];
        msg.flags.push('read');
    });
    unread.declare_bankruptcy();
    exports.update_unread_counts();

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
        exports.update_unread_counts();
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

function consider_bankruptcy() {
    // Until we've handled possibly declaring bankruptcy, don't show
    // unread counts since they only consider messages that are loaded
    // client side and may be different from the numbers reported by
    // the server.

    if (!page_params.furthest_read_time) {
        // We've never read a message.
        exports.enable();
        return;
    }

    var now = new XDate(true).getTime() / 1000;
    if ((page_params.unread_count > 500) &&
        (now - page_params.furthest_read_time > 60 * 60 * 24 * 2)) { // 2 days.
        var unread_info = templates.render('bankruptcy_modal',
                                           {unread_count: page_params.unread_count});
        $('#bankruptcy-unread-count').html(unread_info);
        $('#bankruptcy').modal('show');
    } else {
        exports.enable();
    }
}

exports.initialize = function initialize() {
    consider_bankruptcy();
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread_ui;
}
