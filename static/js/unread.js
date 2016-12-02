// See http://zulip.readthedocs.io/en/latest/pointer.html for notes on
// how this system is designed.

var unread = (function () {

var exports = {};

var unread_mentioned = new Dict();
var unread_privates = new Dict(); // indexed by user_ids_string like 5,7,9
exports.suppress_unread_counts = true;
exports.messages_read_in_narrow = false;

exports.unread_topic_counter = (function () {
    var self = {};

    function str_dict() {
        // Use this when keys are streams and topics.
        return new Dict({fold_case: true});
    }

    function num_dict() {
        // Use this for message ids.
        return new Dict();
    }

    var unread_topics = str_dict(); // dict of stream -> topic -> msg id

    self.clear = function () {
        unread_topics = str_dict();
    };

    self.update = function (stream, subject, new_subject, msg_id) {
        if (unread_topics.has(stream) &&
            unread_topics.get(stream).has(subject) &&
            unread_topics.get(stream).get(subject).get(msg_id)) {
            // Move the unread subject count to the new subject
            unread_topics.get(stream).get(subject).del(msg_id);
            if (unread_topics.get(stream).get(subject).num_items() === 0) {
                unread_topics.get(stream).del(subject);
            }
            unread_topics.get(stream).setdefault(new_subject, num_dict());
            unread_topics.get(stream).get(new_subject).set(msg_id, true);
        }
    };

    self.add = function (stream, subject, msg_id) {
        unread_topics.setdefault(stream, str_dict());
        unread_topics.get(stream).setdefault(subject, num_dict());
        unread_topics.get(stream).get(subject).set(msg_id, true);
    };


    self.del = function (stream, subject, msg_id) {
        var stream_dict = unread_topics.get(stream);
        if (stream_dict) {
            var subject_dict = stream_dict.get(subject);
            if (subject_dict) {
                subject_dict.del(msg_id);
            }
        }
    };

    self.get_counts = function () {
        var res = {};
        res.stream_unread_messages = 0;
        res.stream_count = str_dict();  // hash by stream -> count
        res.subject_count = str_dict(); // hash of hashes (stream, then subject -> count)
        unread_topics.each(function (_, stream) {

            // We track unread counts for streams that may be currently
            // unsubscribed.  Since users may re-subscribe, we don't
            // completely throw away the data.  But we do ignore it here,
            // so that callers have a view of the **current** world.
            if (! stream_data.is_subscribed(stream)) {
                return true;
            }

            if (unread_topics.has(stream)) {
                res.subject_count.set(stream, str_dict());
                var stream_count = 0;
                unread_topics.get(stream).each(function (msgs, subject) {
                    var subject_count = msgs.num_items();
                    res.subject_count.get(stream).set(subject, subject_count);
                    if (!muting.is_topic_muted(stream, subject)) {
                        stream_count += subject_count;
                    }
                });
                res.stream_count.set(stream, stream_count);
                if (stream_data.in_home_view(stream)) {
                    res.stream_unread_messages += stream_count;
                }
            }

        });

        return res;
    };

    self.get = function (stream, subject) {
        var num_unread = 0;
        if (unread_topics.has(stream) &&
            unread_topics.get(stream).has(subject)) {
            num_unread = unread_topics.get(stream).get(subject).num_items();
        }
        return num_unread;
    };

    return self;
}());

exports.message_unread = function (message) {
    if (message === undefined) {
        return false;
    }
    return message.flags === undefined ||
           message.flags.indexOf('read') === -1;
};

exports.update_unread_topics = function (msg, event) {
    if (event.subject !== undefined) {
        exports.unread_topic_counter.update(
            msg.stream,
            msg.subject,
            event.subject,
            msg.id
        );
    }
};

exports.process_loaded_messages = function (messages) {
    _.each(messages, function (message) {
        var unread = exports.message_unread(message);
        if (!unread) {
            return;
        }

        if (message.type === 'private') {
            var user_ids_string = people.emails_strings_to_user_ids_string(message.reply_to);
            if (user_ids_string) {
                unread_privates.setdefault(user_ids_string, new Dict());
                unread_privates.get(user_ids_string).set(message.id, true);
            }
        }

        if (message.type === 'stream') {
            exports.unread_topic_counter.add(
                message.stream,
                message.subject,
                message.id
            );
        }

        if (message.mentioned) {
            unread_mentioned.set(message.id, true);
        }
    });
};

exports.process_read_message = function (message) {

    if (message.type === 'private') {
        var user_ids_string = people.emails_strings_to_user_ids_string(message.reply_to);
        if (user_ids_string) {
            var dict = unread_privates.get(user_ids_string);
            if (dict) {
                dict.del(message.id);
            }
        }
    }

    if (message.type === 'stream') {
        exports.unread_topic_counter.del(
            message.stream,
            message.subject,
            message.id
        );
    }
    unread_mentioned.del(message.id);
};

exports.declare_bankruptcy = function () {
    unread_privates = new Dict();
    exports.unread_topic_counter.clear();
};

exports.num_unread_current_messages = function () {
    var num_unread = 0;

    _.each(current_msg_list.all_messages(), function (msg) {
        if ((msg.id > current_msg_list.selected_id()) && exports.message_unread(msg)) {
            num_unread += 1;
        }
    });

    return num_unread;
};

exports.get_counts = function () {
    var res = {};

    // Return a data structure with various counts.  This function should be
    // pretty cheap, even if you don't care about all the counts, and you
    // should strive to keep it free of side effects on globals or DOM.
    res.private_message_count = 0;
    res.mentioned_message_count = unread_mentioned.num_items();
    res.pm_count = new Dict(); // Hash by email -> count

    // This sets stream_count, subject_count, and home_unread_messages
    var topic_res = exports.unread_topic_counter.get_counts(res);
    res.home_unread_messages = topic_res.stream_unread_messages;
    res.stream_count = topic_res.stream_count;
    res.subject_count = topic_res.subject_count;

    var pm_count = 0;
    unread_privates.each(function (obj, user_ids_string) {
        var count = obj.num_items();
        res.pm_count.set(user_ids_string, count);
        pm_count += count;
    });
    res.private_message_count = pm_count;
    res.home_unread_messages += pm_count;

    if (narrow.active()) {
        res.unread_in_current_view = exports.num_unread_current_messages();
    } else {
        res.unread_in_current_view = res.home_unread_messages;
    }

    return res;
};

exports.num_unread_for_subject = function (stream, subject) {
    return exports.unread_topic_counter.get(stream, subject);
};

exports.num_unread_for_person = function (user_ids_string) {
    if (!user_ids_string) {
        return 0;
    }

    if (!unread_privates.has(user_ids_string)) {
        return 0;
    }
    return unread_privates.get(user_ids_string).num_items();
};

exports.update_unread_counts = function () {
    if (exports.suppress_unread_counts) {
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
    exports.suppress_unread_counts = false;
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
        if (viewport.bottom_message_visible()) {
            exports.mark_current_list_as_read();
        }
    } else {
        exports.mark_messages_as_read(viewport.visible_messages(true));
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
                   stream_name: stream
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
               stream_name: stream
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
        unread.enable();
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
        unread.enable();
    }
}

exports.initialize = function initialize() {
    consider_bankruptcy();
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread;
}
