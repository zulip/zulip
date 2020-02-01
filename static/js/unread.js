const Dict = require('./dict').Dict;
const FoldDict = require('./fold_dict').FoldDict;
const IntDict = require('./int_dict').IntDict;

// The unread module tracks the message IDs and locations of the
// user's unread messages.  The tracking is initialized with
// server-provided data of the total set of unread messages in the
// user's history via page_params.unread_msgs (well, it cuts off at
// MAX_UNREAD_MESSAGES unreads for performance reasons).  As a result,
// it can contain many thousands of messages that we don't have full
// data for in `message_store`, so we cannot in general look these
// messages up there.

// See https://zulip.readthedocs.io/en/latest/subsystems/pointer.html
// for more details on how this system is designed.

exports.suppress_unread_counts = true;
exports.set_suppress_unread_counts = function (value) {
    exports.suppress_unread_counts = value;
};
exports.messages_read_in_narrow = false;
exports.set_messages_read_in_narrow = function (value) {
    exports.messages_read_in_narrow = value;
};

const unread_messages = new Set();

function make_bucketer(options) {
    const self = {};
    const key_to_bucket = new options.KeyDict();
    const reverse_lookup = new IntDict();

    self.clear = function () {
        key_to_bucket.clear();
        reverse_lookup.clear();
    };

    self.add = function (opts) {
        const bucket_key = opts.bucket_key;
        const item_id = opts.item_id;
        const add_callback = opts.add_callback;

        let bucket = key_to_bucket.get(bucket_key);
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

    self.delete = function (item_id) {
        const bucket = reverse_lookup.get(item_id);
        if (bucket) {
            bucket.delete(item_id);
            reverse_lookup.delete(item_id);
        }
    };

    self.get_bucket = function (bucket_key) {
        return key_to_bucket.get(bucket_key);
    };

    self.keys = function () {
        return key_to_bucket.keys();
    };

    self.values = function () {
        return key_to_bucket.values();
    };

    self[Symbol.iterator] = function () {
        return key_to_bucket[Symbol.iterator]();
    };

    return self;
}

exports.unread_pm_counter = (function () {
    const self = {};

    const bucketer = make_bucketer({
        KeyDict: Dict,
        make_bucket: () => new Set(),
    });

    self.clear = function () {
        bucketer.clear();
    };

    self.set_pms = function (pms) {
        _.each(pms, function (obj) {
            const user_ids_string = obj.sender_id.toString();
            self.set_message_ids(user_ids_string, obj.unread_message_ids);
        });
    };

    self.set_huddles = function (huddles) {
        _.each(huddles, function (obj) {
            const user_ids_string = people.pm_lookup_key(obj.user_ids_string);
            self.set_message_ids(user_ids_string, obj.unread_message_ids);
        });
    };

    self.set_message_ids = function (user_ids_string, unread_message_ids) {
        _.each(unread_message_ids, function (msg_id) {
            bucketer.add({
                bucket_key: user_ids_string,
                item_id: msg_id,
            });
        });
    };

    self.add = function (message) {
        const user_ids_string = people.pm_reply_user_string(message);
        if (user_ids_string) {
            bucketer.add({
                bucket_key: user_ids_string,
                item_id: message.id,
            });
        }
    };

    self.delete = function (message_id) {
        bucketer.delete(message_id);
    };

    self.get_counts = function () {
        const pm_dict = new Dict(); // Hash by user_ids_string -> count
        let total_count = 0;
        for (const [user_ids_string, id_set] of bucketer) {
            const count = id_set.size;
            pm_dict.set(user_ids_string, count);
            total_count += count;
        }
        return {
            total_count: total_count,
            pm_dict: pm_dict,
        };
    };

    self.num_unread = function (user_ids_string) {
        if (!user_ids_string) {
            return 0;
        }

        const bucket = bucketer.get_bucket(user_ids_string);

        if (!bucket) {
            return 0;
        }
        return bucket.size;
    };

    self.get_msg_ids = function () {
        const lists = [];

        for (const id_set of bucketer.values()) {
            const members = Array.from(id_set);
            lists.push(members);
        }

        const ids = [].concat.apply([], lists);

        return util.sorted_ids(ids);
    };

    self.get_msg_ids_for_person = function (user_ids_string) {
        if (!user_ids_string) {
            return [];
        }

        const bucket = bucketer.get_bucket(user_ids_string);

        if (!bucket) {
            return [];
        }

        const ids = Array.from(bucket);
        return util.sorted_ids(ids);
    };

    return self;
}());

function make_per_stream_bucketer() {
    return make_bucketer({
        KeyDict: FoldDict, // bucket keys are topics
        make_bucket: () => new Set(),
    });
}

exports.unread_topic_counter = (function () {
    const self = {};

    const bucketer = make_bucketer({
        KeyDict: IntDict, // bucket keys are stream_ids
        make_bucket: make_per_stream_bucketer,
    });

    self.clear = function () {
        bucketer.clear();
    };


    self.set_streams = function (objs) {
        _.each(objs, function (obj) {
            const stream_id = obj.stream_id;
            const topic = obj.topic;
            const unread_message_ids = obj.unread_message_ids;

            _.each(unread_message_ids, function (msg_id) {
                self.add(stream_id, topic, msg_id);
            });
        });
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

    self.delete = function (msg_id) {
        bucketer.delete(msg_id);
    };

    self.get_counts = function () {
        const res = {};
        res.stream_unread_messages = 0;
        res.stream_count = new IntDict();  // hash by stream_id -> count
        for (const [stream_id, per_stream_bucketer] of bucketer) {

            // We track unread counts for streams that may be currently
            // unsubscribed.  Since users may re-subscribe, we don't
            // completely throw away the data.  But we do ignore it here,
            // so that callers have a view of the **current** world.
            const sub = stream_data.get_sub_by_id(stream_id);
            if (!sub || !stream_data.is_subscribed(sub.name)) {
                continue;
            }

            let stream_count = 0;
            for (const [topic, msgs] of per_stream_bucketer) {
                const topic_count = msgs.size;
                if (!muting.is_topic_muted(stream_id, topic)) {
                    stream_count += topic_count;
                }
            }
            res.stream_count.set(stream_id, stream_count);
            if (!stream_data.is_muted(stream_id)) {
                res.stream_unread_messages += stream_count;
            }

        }

        return res;
    };

    self.get_missing_topics = function (opts) {
        const stream_id = opts.stream_id;
        const topic_dict = opts.topic_dict;

        const per_stream_bucketer = bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return [];
        }

        let topic_names = Array.from(per_stream_bucketer.keys());

        topic_names = _.reject(topic_names, function (topic_name) {
            return topic_dict.has(topic_name);
        });

        const result = _.map(topic_names, function (topic_name) {
            const msgs = per_stream_bucketer.get_bucket(topic_name);

            return {
                pretty_name: topic_name,
                message_id: Math.max(...Array.from(msgs)),
            };
        });

        return result;
    };

    self.get_stream_count = function (stream_id) {
        let stream_count = 0;

        const per_stream_bucketer = bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return 0;
        }

        const sub = stream_data.get_sub_by_id(stream_id);
        for (const [topic, msgs] of per_stream_bucketer) {
            if (sub && !muting.is_topic_muted(stream_id, topic)) {
                stream_count += msgs.size;
            }
        }

        return stream_count;
    };

    self.get = function (stream_id, topic) {
        const per_stream_bucketer = bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return 0;
        }

        const topic_bucket = per_stream_bucketer.get_bucket(topic);
        if (!topic_bucket) {
            return 0;
        }

        return topic_bucket.size;
    };

    self.get_msg_ids_for_stream = function (stream_id) {
        const per_stream_bucketer = bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return [];
        }

        const topic_lists = [];
        const sub = stream_data.get_sub_by_id(stream_id);
        for (const [topic, msgs] of per_stream_bucketer) {
            if (sub && !muting.is_topic_muted(stream_id, topic)) {
                topic_lists.push(Array.from(msgs));
            }
        }

        const ids = [].concat.apply([], topic_lists);

        return util.sorted_ids(ids);
    };

    self.get_msg_ids_for_topic = function (stream_id, topic) {
        const per_stream_bucketer = bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return [];
        }

        const topic_bucket = per_stream_bucketer.get_bucket(topic);
        if (!topic_bucket) {
            return [];
        }

        const ids = Array.from(topic_bucket);
        return util.sorted_ids(ids);
    };


    self.topic_has_any_unread = function (stream_id, topic) {
        const per_stream_bucketer = bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return false;
        }

        const id_set = per_stream_bucketer.get_bucket(topic);
        if (!id_set) {
            return false;
        }

        return id_set.size !== 0;
    };

    return self;
}());

exports.unread_mentions_counter = new Set();

exports.message_unread = function (message) {
    if (message === undefined) {
        return false;
    }
    return message.unread;
};

exports.get_unread_message_ids = function (message_ids) {
    return _.filter(message_ids, message_id => unread_messages.has(message_id));
};

exports.get_unread_messages = function (messages) {
    return _.filter(messages, function (message) {
        return unread_messages.has(message.id);
    });
};

exports.update_unread_topics = function (msg, event) {
    const new_topic = util.get_edit_event_topic(event);

    if (new_topic === undefined) {
        return;
    }

    if (!unread_messages.has(msg.id)) {
        return;
    }

    exports.unread_topic_counter.delete(
        msg.id
    );

    exports.unread_topic_counter.add(
        msg.stream_id,
        new_topic,
        msg.id
    );
};

exports.process_loaded_messages = function (messages) {
    _.each(messages, function (message) {
        if (!message.unread) {
            return;
        }

        unread_messages.add(message.id);

        if (message.type === 'private') {
            exports.unread_pm_counter.add(message);
        }

        if (message.type === 'stream') {
            exports.unread_topic_counter.add(
                message.stream_id,
                util.get_message_topic(message),
                message.id
            );
        }

        const is_unmuted_mention = message.type === 'stream' && message.mentioned &&
                                   !muting.is_topic_muted(message.stream_id,
                                                          util.get_message_topic(message));
        if (message.mentioned_me_directly || is_unmuted_mention) {
            exports.unread_mentions_counter.add(message.id);
        }
    });
};

exports.mark_as_read = function (message_id) {
    // We don't need to check anything about the message, since all
    // the following methods are cheap and work fine even if message_id
    // was never set to unread.
    exports.unread_pm_counter.delete(message_id);
    exports.unread_topic_counter.delete(message_id);
    exports.unread_mentions_counter.delete(message_id);
    unread_messages.delete(message_id);

    const message = message_store.get(message_id);
    if (message) {
        message.unread = false;
    }
};

exports.declare_bankruptcy = function () {
    exports.unread_pm_counter.clear();
    exports.unread_topic_counter.clear();
    exports.unread_mentions_counter.clear();
    unread_messages.clear();
};

exports.get_counts = function () {
    const res = {};

    // Return a data structure with various counts.  This function should be
    // pretty cheap, even if you don't care about all the counts, and you
    // should strive to keep it free of side effects on globals or DOM.
    res.private_message_count = 0;
    res.mentioned_message_count = exports.unread_mentions_counter.size;

    // This sets stream_count, topic_count, and home_unread_messages
    const topic_res = exports.unread_topic_counter.get_counts();
    res.home_unread_messages = topic_res.stream_unread_messages;
    res.stream_count = topic_res.stream_count;

    const pm_res = exports.unread_pm_counter.get_counts();
    res.pm_count = pm_res.pm_dict;
    res.private_message_count = pm_res.total_count;
    res.home_unread_messages += pm_res.total_count;

    return res;
};

// Saves us from calling to get_counts() when we can avoid it.
exports.calculate_notifiable_count = function (res) {
    let new_message_count = 0;

    const only_show_notifiable = page_params.desktop_icon_count_display ===
        settings_notifications.desktop_icon_count_display_values.notifiable.code;
    const no_notifications = page_params.desktop_icon_count_display ===
        settings_notifications.desktop_icon_count_display_values.none.code;
    if (only_show_notifiable) {
        // DESKTOP_ICON_COUNT_DISPLAY_NOTIFIABLE
        new_message_count = res.mentioned_message_count + res.private_message_count;
    } else if (no_notifications) {
        // DESKTOP_ICON_COUNT_DISPLAY_NONE
        new_message_count = 0;
    } else {
        // DESKTOP_ICON_COUNT_DISPLAY_MESSAGES
        new_message_count = res.home_unread_messages;
    }
    return new_message_count;
};

exports.get_notifiable_count = function () {
    const res = exports.get_counts();
    return exports.calculate_notifiable_count(res);
};

exports.num_unread_for_stream = function (stream_id) {
    return exports.unread_topic_counter.get_stream_count(stream_id);
};

exports.num_unread_for_topic = function (stream_id, topic_name) {
    return exports.unread_topic_counter.get(stream_id, topic_name);
};

exports.topic_has_any_unread = function (stream_id, topic) {
    return exports.unread_topic_counter.topic_has_any_unread(stream_id, topic);
};

exports.num_unread_for_person = function (user_ids_string) {
    return exports.unread_pm_counter.num_unread(user_ids_string);
};

exports.get_msg_ids_for_stream = function (stream_id) {
    return exports.unread_topic_counter.get_msg_ids_for_stream(stream_id);
};

exports.get_msg_ids_for_topic = function (stream_id, topic_name) {
    return exports.unread_topic_counter.get_msg_ids_for_topic(stream_id, topic_name);
};

exports.get_msg_ids_for_person = function (user_ids_string) {
    return exports.unread_pm_counter.get_msg_ids_for_person(user_ids_string);
};

exports.get_msg_ids_for_private = function () {
    return exports.unread_pm_counter.get_msg_ids();
};

exports.get_msg_ids_for_mentions = function () {
    const ids = Array.from(exports.unread_mentions_counter);

    return util.sorted_ids(ids);
};

exports.get_all_msg_ids = function () {
    const ids = Array.from(unread_messages);

    return util.sorted_ids(ids);
};

exports.get_missing_topics = function (opts) {
    return exports.unread_topic_counter.get_missing_topics(opts);
};

exports.get_msg_ids_for_starred = function () {
    // This is here for API consistency sake--we never
    // have unread starred messages.  (Some day we may ironically
    // want to make starring the same as mark-as-unread, but
    // for now starring === reading.)
    return [];
};

exports.initialize = function () {
    const unread_msgs = page_params.unread_msgs;

    exports.unread_pm_counter.set_huddles(unread_msgs.huddles);
    exports.unread_pm_counter.set_pms(unread_msgs.pms);
    exports.unread_topic_counter.set_streams(unread_msgs.streams);
    _.each(unread_msgs.mentions, message_id => exports.unread_mentions_counter.add(message_id));

    _.each(unread_msgs.huddles, function (obj) {
        _.each(obj.unread_message_ids, message_id => unread_messages.add(message_id));
    });
    _.each(unread_msgs.pms, function (obj) {
        _.each(obj.unread_message_ids, message_id => unread_messages.add(message_id));
    });
    _.each(unread_msgs.streams, function (obj) {
        _.each(obj.unread_message_ids, message_id => unread_messages.add(message_id));
    });
    _.each(unread_msgs.mentions, message_id => unread_messages.add(message_id));
};

window.unread = exports;
