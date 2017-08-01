// See http://zulip.readthedocs.io/en/latest/pointer.html for notes on
// how this system is designed.

var unread = (function () {

var exports = {};

exports.suppress_unread_counts = true;
exports.messages_read_in_narrow = false;

exports.unread_pm_counter = (function () {
    var self = {};
    var unread_privates = new Dict(); // indexed by user_ids_string like 5,7,9

    self.clear = function () {
        unread_privates = new Dict();
    };

    self.add = function (message) {
        var user_ids_string = people.pm_reply_user_string(message);
        if (user_ids_string) {
            unread_privates.setdefault(user_ids_string, new Dict());
            unread_privates.get(user_ids_string).set(message.id, true);
        }
    };

    self.del = function (message) {
        var user_ids_string = people.pm_reply_user_string(message);
        if (user_ids_string) {
            var dict = unread_privates.get(user_ids_string);
            if (dict) {
                dict.del(message.id);
            }
        }
    };

    self.get_counts = function () {
        var pm_dict = new Dict(); // Hash by user_ids_string -> count
        var total_count = 0;
        unread_privates.each(function (obj, user_ids_string) {
            var count = obj.num_items();
            pm_dict.set(user_ids_string, count);
            total_count += count;
        });
        return {
            total_count: total_count,
            pm_dict: pm_dict,
        };
    };

    self.num_unread = function (user_ids_string) {
        if (!user_ids_string) {
            return 0;
        }

        if (!unread_privates.has(user_ids_string)) {
            return 0;
        }
        return unread_privates.get(user_ids_string).num_items();
    };

    return self;
}());

exports.unread_topic_counter = (function () {
    var self = {};

    function str_dict() {
        // Use this when keys are topics
        return new Dict({fold_case: true});
    }

    function num_dict() {
        // Use this for message ids.
        return new Dict();
    }

    var unread_topics = num_dict(); // dict of stream -> topic -> msg id

    self.clear = function () {
        unread_topics = num_dict();
    };

    self.update = function (stream_id, topic, new_topic, msg_id) {
        if (unread_topics.has(stream_id) &&
            unread_topics.get(stream_id).has(topic) &&
            unread_topics.get(stream_id).get(topic).get(msg_id)) {
            // Move the unread topic count to the new topic
            unread_topics.get(stream_id).get(topic).del(msg_id);
            if (unread_topics.get(stream_id).get(topic).num_items() === 0) {
                unread_topics.get(stream_id).del(topic);
            }
            unread_topics.get(stream_id).setdefault(new_topic, num_dict());
            unread_topics.get(stream_id).get(new_topic).set(msg_id, true);
        }
    };

    self.add = function (stream_id, topic, msg_id) {
        unread_topics.setdefault(stream_id, str_dict());
        unread_topics.get(stream_id).setdefault(topic, num_dict());
        unread_topics.get(stream_id).get(topic).set(msg_id, true);
    };


    self.del = function (stream_id, topic, msg_id) {
        var stream_dict = unread_topics.get(stream_id);
        if (stream_dict) {
            var topic_dict = stream_dict.get(topic);
            if (topic_dict) {
                topic_dict.del(msg_id);
            }
        }
    };

    self.get_counts = function () {
        var res = {};
        res.stream_unread_messages = 0;
        res.stream_count = num_dict();  // hash by stream_id -> count
        res.topic_count = num_dict(); // hash of hashes (stream_id, then topic -> count)
        unread_topics.each(function (_, stream_id) {

            // We track unread counts for streams that may be currently
            // unsubscribed.  Since users may re-subscribe, we don't
            // completely throw away the data.  But we do ignore it here,
            // so that callers have a view of the **current** world.
            var sub = stream_data.get_sub_by_id(stream_id);
            if (!sub || !stream_data.is_subscribed(sub.name)) {
                return true;
            }

            if (unread_topics.has(stream_id)) {
                res.topic_count.set(stream_id, str_dict());
                var stream_count = 0;
                unread_topics.get(stream_id).each(function (msgs, topic) {
                    var topic_count = msgs.num_items();
                    res.topic_count.get(stream_id).set(topic, topic_count);
                    if (!muting.is_topic_muted(sub.name, topic)) {
                        stream_count += topic_count;
                    }
                });
                res.stream_count.set(stream_id, stream_count);
                if (stream_data.in_home_view(stream_id)) {
                    res.stream_unread_messages += stream_count;
                }
            }

        });

        return res;
    };

    self.get_stream_count = function (stream_id) {
        var stream_count = 0;

        if (!unread_topics.has(stream_id)) {
            return 0;
        }

        unread_topics.get(stream_id).each(function (msgs, topic) {
            var sub = stream_data.get_sub_by_id(stream_id);
            if (sub && !muting.is_topic_muted(sub.name, topic)) {
                stream_count += msgs.num_items();
            }
        });

        return stream_count;
    };

    self.get = function (stream_id, topic) {
        var num_unread = 0;
        if (unread_topics.has(stream_id) &&
            unread_topics.get(stream_id).has(topic)) {
            num_unread = unread_topics.get(stream_id).get(topic).num_items();
        }
        return num_unread;
    };

    self.topic_has_any_unread = function (stream_id, topic) {
        var stream_dct = unread_topics.get(stream_id);

        if (!stream_dct) {
            return false;
        }

        var topic_dct = stream_dct.get(topic);
        if (!topic_dct) {
            return false;
        }

        return !topic_dct.is_empty();
    };

    return self;
}());

exports.unread_mentions_counter = (function () {
    var self = {};
    var mentions = new Dict(); // msg_id -> true

    self.clear = function () {
        mentions = new Dict();
    };

    self.add = function (message_id) {
        mentions.set(message_id, true);
    };

    self.del = function (message_id) {
        mentions.del(message_id);
    };

    self.count = function () {
        return mentions.num_items();
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
            msg.stream_id,
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
            exports.unread_pm_counter.add(message);
        }

        if (message.type === 'stream') {
            exports.unread_topic_counter.add(
                message.stream_id,
                message.subject,
                message.id
            );
        }

        if (message.mentioned) {
            exports.unread_mentions_counter.add(message.id);
        }
    });
};

exports.process_read_message = function (message) {

    if (message.type === 'private') {
        exports.unread_pm_counter.del(message);
    }

    if (message.type === 'stream') {
        if (message.stream_id === undefined) {
            blueslip.error('No stream_id found for message ' + message.id);
            return;
        }
        exports.unread_topic_counter.del(
            message.stream_id,
            message.subject,
            message.id
        );
    }

    exports.unread_mentions_counter.del(message.id);
};

exports.declare_bankruptcy = function () {
    exports.unread_pm_counter.clear();
    exports.unread_topic_counter.clear();
    exports.unread_mentions_counter.clear();
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
    res.mentioned_message_count = exports.unread_mentions_counter.count();

    // This sets stream_count, topic_count, and home_unread_messages
    var topic_res = exports.unread_topic_counter.get_counts();
    res.home_unread_messages = topic_res.stream_unread_messages;
    res.stream_count = topic_res.stream_count;
    res.topic_count = topic_res.topic_count;

    var pm_res = exports.unread_pm_counter.get_counts();
    res.pm_count = pm_res.pm_dict;
    res.private_message_count = pm_res.total_count;
    res.home_unread_messages += pm_res.total_count;

    if (narrow_state.active()) {
        res.unread_in_current_view = exports.num_unread_current_messages();
    } else {
        res.unread_in_current_view = res.home_unread_messages;
    }

    return res;
};

exports.num_unread_for_stream = function (stream_id) {
    return exports.unread_topic_counter.get_stream_count(stream_id);
};

exports.num_unread_for_topic = function (stream_id, subject) {
    return exports.unread_topic_counter.get(stream_id, subject);
};

exports.topic_has_any_unread = function (stream_id, topic) {
    return exports.unread_topic_counter.topic_has_any_unread(stream_id, topic);
};

exports.num_unread_for_person = function (user_ids_string) {
    return exports.unread_pm_counter.num_unread(user_ids_string);
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread;
}
