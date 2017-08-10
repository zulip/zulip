// See http://zulip.readthedocs.io/en/latest/pointer.html for notes on
// how this system is designed.

var unread = (function () {

var exports = {};

var unread_messages = new Dict();

exports.suppress_unread_counts = true;
exports.messages_read_in_narrow = false;

function make_id_set() {
    /* This is just a basic set class where
       elements should be numeric ids.
    */

    var self = {};
    var ids = new Dict();

    self.clear = function () {
        ids.clear();
    };

    self.add = function (id) {
        ids.set(id, true);
    };

    self.del = function (id) {
        ids.del(id);
    };

    self.count = function () {
        return ids.num_items();
    };

    self.is_empty = function () {
        return ids.is_empty();
    };

    return self;
}

function make_bucketer(options) {
    var self = {};

    var key_to_bucket = new Dict({fold_case: options.fold_case});
    var reverse_lookup = new Dict();

    self.clear = function () {
        key_to_bucket.clear();
        reverse_lookup.clear();
    };

    self.add = function (opts) {
        var bucket_key = opts.bucket_key;
        var item_id = opts.item_id;
        var add_callback = opts.add_callback;

        var bucket = key_to_bucket.get(bucket_key);
        if (!bucket) {
            bucket = options.make_bucket();
            key_to_bucket.set(bucket_key, bucket);
        }
        if (add_callback) {
            add_callback(bucket, item_id);
        } else {
            bucket.add(item_id);
        }
        reverse_lookup.set(item_id, bucket);
    };

    self.del = function (item_id) {
        var bucket = reverse_lookup.get(item_id);
        if (bucket) {
            bucket.del(item_id);
            reverse_lookup.del(item_id);
        }
    };

    self.get_bucket = function (bucket_key) {
        return key_to_bucket.get(bucket_key);
    };

    self.each = function (callback) {
        key_to_bucket.each(callback);
    };

    return self;
}

exports.unread_pm_counter = (function () {
    var self = {};

    var bucketer = make_bucketer({
        fold_case: false,
        make_bucket: make_id_set,
    });

    self.clear = function () {
        bucketer.clear();
    };

    self.add = function (message) {
        var user_ids_string = people.pm_reply_user_string(message);
        if (user_ids_string) {
            bucketer.add({
                bucket_key: user_ids_string,
                item_id: message.id,
            });
        }
    };

    self.del = function (message_id) {
        bucketer.del(message_id);
    };

    self.get_counts = function () {
        var pm_dict = new Dict(); // Hash by user_ids_string -> count
        var total_count = 0;
        bucketer.each(function (id_set, user_ids_string) {
            var count = id_set.count();
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

        var bucket = bucketer.get_bucket(user_ids_string);

        if (!bucket) {
            return 0;
        }
        return bucket.count();
    };

    return self;
}());

function make_per_stream_bucketer() {
    return make_bucketer({
        fold_case: true, // bucket keys are topics
        make_bucket: make_id_set,
    });
}

exports.unread_topic_counter = (function () {
    var self = {};

    var bucketer = make_bucketer({
        fold_case: false, // bucket keys are stream_ids
        make_bucket: make_per_stream_bucketer,
    });

    self.clear = function () {
        bucketer.clear();
    };

    self.add = function (stream_id, topic, msg_id) {
        bucketer.add({
            bucket_key: stream_id,
            item_id: msg_id,
            add_callback: function (per_stream_bucketer) {
                per_stream_bucketer.add({
                    bucket_key: topic,
                    item_id: msg_id,
                });
            },
        });
    };

    self.del = function (msg_id) {
        bucketer.del(msg_id);
    };

    function str_dict() {
        // Use this when keys are topics
        return new Dict({fold_case: true});
    }

    function num_dict() {
        // Use this for stream ids.
        return new Dict();
    }

    self.get_counts = function () {
        var res = {};
        res.stream_unread_messages = 0;
        res.stream_count = num_dict();  // hash by stream_id -> count
        res.topic_count = num_dict(); // hash of hashes (stream_id, then topic -> count)
        bucketer.each(function (per_stream_bucketer, stream_id) {

            // We track unread counts for streams that may be currently
            // unsubscribed.  Since users may re-subscribe, we don't
            // completely throw away the data.  But we do ignore it here,
            // so that callers have a view of the **current** world.
            var sub = stream_data.get_sub_by_id(stream_id);
            if (!sub || !stream_data.is_subscribed(sub.name)) {
                return;
            }

            res.topic_count.set(stream_id, str_dict());
            var stream_count = 0;
            per_stream_bucketer.each(function (msgs, topic) {
                var topic_count = msgs.count();
                res.topic_count.get(stream_id).set(topic, topic_count);
                if (!muting.is_topic_muted(sub.name, topic)) {
                    stream_count += topic_count;
                }
            });
            res.stream_count.set(stream_id, stream_count);
            if (stream_data.in_home_view(stream_id)) {
                res.stream_unread_messages += stream_count;
            }

        });

        return res;
    };

    self.get_stream_count = function (stream_id) {
        var stream_count = 0;

        var per_stream_bucketer = bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return 0;
        }

        per_stream_bucketer.each(function (msgs, topic) {
            var sub = stream_data.get_sub_by_id(stream_id);
            if (sub && !muting.is_topic_muted(sub.name, topic)) {
                stream_count += msgs.count();
            }
        });

        return stream_count;
    };

    self.get = function (stream_id, topic) {
        var per_stream_bucketer = bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return 0;
        }

        var topic_bucket = per_stream_bucketer.get_bucket(topic);
        if (!topic_bucket) {
            return 0;
        }

        return topic_bucket.count();
    };

    self.topic_has_any_unread = function (stream_id, topic) {
        var per_stream_bucketer = bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return false;
        }

        var id_set = per_stream_bucketer.get_bucket(topic);
        if (!id_set) {
            return false;
        }

        return !id_set.is_empty();
    };

    return self;
}());

exports.unread_mentions_counter = make_id_set();

exports.message_unread = function (message) {
    if (message === undefined) {
        return false;
    }
    return message.flags === undefined ||
           message.flags.indexOf('read') === -1;
};

exports.id_flagged_as_unread = function (message_id) {
    return unread_messages.has(message_id);
};

exports.update_unread_topics = function (msg, event) {
    if (event.subject === undefined) {
        return;
    }

    if (!unread_messages.has(msg.id)) {
        return;
    }

    exports.unread_topic_counter.del(
        msg.id
    );

    exports.unread_topic_counter.add(
        msg.stream_id,
        event.subject,
        msg.id
    );
};

exports.process_loaded_messages = function (messages) {
    _.each(messages, function (message) {
        var unread = exports.message_unread(message);
        if (!unread) {
            return;
        }

        unread_messages.set(message.id, true);

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

exports.mark_as_read = function (message_id) {
    // We don't need to check anything about the message, since all
    // the following methods are cheap and work fine even if message_id
    // was never set to unread.
    exports.unread_pm_counter.del(message_id);
    exports.unread_topic_counter.del(message_id);
    exports.unread_mentions_counter.del(message_id);
    unread_messages.del(message_id);
};

exports.declare_bankruptcy = function () {
    exports.unread_pm_counter.clear();
    exports.unread_topic_counter.clear();
    exports.unread_mentions_counter.clear();
    unread_messages.clear();
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

exports.set_read_flag = function (message) {
    /*
        Our data structures allow us to know if a message_id is unread/read,
        but we also need to set message.unread for our rendering code.

        We also have code that uses message.flags, so we maintain that data
        as well. The server sends us flags (e.g. ['read', 'starred']), so
        our code on the "edges" needs that representation.

        It is kind of painful to have three different representations, but
        we fortunately only set read/unread in a few places in our code.
    */
    message.flags = message.flags || [];
    if (!_.contains(message.flags, 'read')) {
        message.flags.push('read');
    }
    message.unread = false;
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = unread;
}
