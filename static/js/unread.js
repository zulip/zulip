"use strict";

const FoldDict = require("./fold_dict").FoldDict;
const people = require("./people");
const util = require("./util");

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

exports.messages_read_in_narrow = false;
exports.set_messages_read_in_narrow = function (value) {
    exports.messages_read_in_narrow = value;
};

const unread_messages = new Set();

class Bucketer {
    reverse_lookup = new Map();

    constructor(options) {
        this.key_to_bucket = new options.KeyDict();
        this.make_bucket = options.make_bucket;
    }

    clear() {
        this.key_to_bucket.clear();
        this.reverse_lookup.clear();
    }

    add(opts) {
        const bucket_key = opts.bucket_key;
        const item_id = opts.item_id;
        const add_callback = opts.add_callback;

        let bucket = this.key_to_bucket.get(bucket_key);
        if (!bucket) {
            bucket = this.make_bucket();
            this.key_to_bucket.set(bucket_key, bucket);
        }
        if (add_callback) {
            add_callback(bucket, item_id);
        } else {
            bucket.add(item_id);
        }
        this.reverse_lookup.set(item_id, bucket);
    }

    delete(item_id) {
        const bucket = this.reverse_lookup.get(item_id);
        if (bucket) {
            bucket.delete(item_id);
            this.reverse_lookup.delete(item_id);
        }
    }

    get_bucket(bucket_key) {
        return this.key_to_bucket.get(bucket_key);
    }

    keys() {
        return this.key_to_bucket.keys();
    }

    values() {
        return this.key_to_bucket.values();
    }

    [Symbol.iterator]() {
        return this.key_to_bucket[Symbol.iterator]();
    }
}

class UnreadPMCounter {
    bucketer = new Bucketer({
        KeyDict: Map,
        make_bucket: () => new Set(),
    });

    clear() {
        this.bucketer.clear();
    }

    set_pms(pms) {
        for (const obj of pms) {
            const user_ids_string = obj.sender_id.toString();
            this.set_message_ids(user_ids_string, obj.unread_message_ids);
        }
    }

    set_huddles(huddles) {
        for (const obj of huddles) {
            const user_ids_string = people.pm_lookup_key(obj.user_ids_string);
            this.set_message_ids(user_ids_string, obj.unread_message_ids);
        }
    }

    set_message_ids(user_ids_string, unread_message_ids) {
        for (const msg_id of unread_message_ids) {
            this.bucketer.add({
                bucket_key: user_ids_string,
                item_id: msg_id,
            });
        }
    }

    add(message) {
        const user_ids_string = people.pm_reply_user_string(message);
        if (user_ids_string) {
            this.bucketer.add({
                bucket_key: user_ids_string,
                item_id: message.id,
            });
        }
    }

    delete(message_id) {
        this.bucketer.delete(message_id);
    }

    get_counts() {
        const pm_dict = new Map(); // Hash by user_ids_string -> count
        let total_count = 0;
        for (const [user_ids_string, id_set] of this.bucketer) {
            const count = id_set.size;
            pm_dict.set(user_ids_string, count);
            total_count += count;
        }
        return {
            total_count,
            pm_dict,
        };
    }

    num_unread(user_ids_string) {
        if (!user_ids_string) {
            return 0;
        }

        const bucket = this.bucketer.get_bucket(user_ids_string);

        if (!bucket) {
            return 0;
        }
        return bucket.size;
    }

    get_msg_ids() {
        const ids = [];

        for (const id_set of this.bucketer.values()) {
            for (const id of id_set) {
                ids.push(id);
            }
        }

        return util.sorted_ids(ids);
    }

    get_msg_ids_for_person(user_ids_string) {
        if (!user_ids_string) {
            return [];
        }

        const bucket = this.bucketer.get_bucket(user_ids_string);

        if (!bucket) {
            return [];
        }

        const ids = Array.from(bucket);
        return util.sorted_ids(ids);
    }
}
exports.unread_pm_counter = new UnreadPMCounter();

function make_per_stream_bucketer() {
    return new Bucketer({
        KeyDict: FoldDict, // bucket keys are topics
        make_bucket: () => new Set(),
    });
}

class UnreadTopicCounter {
    bucketer = new Bucketer({
        KeyDict: Map, // bucket keys are stream_ids
        make_bucket: make_per_stream_bucketer,
    });

    clear() {
        this.bucketer.clear();
    }

    set_streams(objs) {
        for (const obj of objs) {
            const stream_id = obj.stream_id;
            const topic = obj.topic;
            const unread_message_ids = obj.unread_message_ids;

            for (const msg_id of unread_message_ids) {
                this.add(stream_id, topic, msg_id);
            }
        }
    }

    add(stream_id, topic, msg_id) {
        this.bucketer.add({
            bucket_key: stream_id,
            item_id: msg_id,
            add_callback(per_stream_bucketer) {
                per_stream_bucketer.add({
                    bucket_key: topic,
                    item_id: msg_id,
                });
            },
        });
    }

    delete(msg_id) {
        this.bucketer.delete(msg_id);
    }

    get_counts() {
        const res = {};
        res.stream_unread_messages = 0;
        res.stream_count = new Map(); // hash by stream_id -> count
        for (const [stream_id, per_stream_bucketer] of this.bucketer) {
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
    }

    get_missing_topics(opts) {
        const stream_id = opts.stream_id;
        const topic_dict = opts.topic_dict;

        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return [];
        }

        let topic_names = Array.from(per_stream_bucketer.keys());

        topic_names = topic_names.filter((topic_name) => !topic_dict.has(topic_name));

        const result = topic_names.map((topic_name) => {
            const msgs = per_stream_bucketer.get_bucket(topic_name);

            return {
                pretty_name: topic_name,
                message_id: Math.max(...Array.from(msgs)),
            };
        });

        return result;
    }

    get_stream_count(stream_id) {
        let stream_count = 0;

        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);

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
    }

    get(stream_id, topic) {
        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return 0;
        }

        const topic_bucket = per_stream_bucketer.get_bucket(topic);
        if (!topic_bucket) {
            return 0;
        }

        return topic_bucket.size;
    }

    get_msg_ids_for_stream(stream_id) {
        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return [];
        }

        const ids = [];
        const sub = stream_data.get_sub_by_id(stream_id);
        for (const [topic, id_set] of per_stream_bucketer) {
            if (sub && !muting.is_topic_muted(stream_id, topic)) {
                for (const id of id_set) {
                    ids.push(id);
                }
            }
        }

        return util.sorted_ids(ids);
    }

    get_msg_ids_for_topic(stream_id, topic) {
        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return [];
        }

        const topic_bucket = per_stream_bucketer.get_bucket(topic);
        if (!topic_bucket) {
            return [];
        }

        const ids = Array.from(topic_bucket);
        return util.sorted_ids(ids);
    }

    topic_has_any_unread(stream_id, topic) {
        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return false;
        }

        const id_set = per_stream_bucketer.get_bucket(topic);
        if (!id_set) {
            return false;
        }

        return id_set.size !== 0;
    }
}
exports.unread_topic_counter = new UnreadTopicCounter();

exports.unread_mentions_counter = new Set();

exports.message_unread = function (message) {
    if (message === undefined) {
        return false;
    }
    return message.unread;
};

exports.get_unread_message_ids = function (message_ids) {
    return message_ids.filter((message_id) => unread_messages.has(message_id));
};

exports.get_unread_messages = function (messages) {
    return messages.filter((message) => unread_messages.has(message.id));
};

exports.update_unread_topics = function (msg, event) {
    const new_topic = util.get_edit_event_topic(event);
    const {new_stream_id} = event;

    if (new_topic === undefined && new_stream_id === undefined) {
        return;
    }

    if (!unread_messages.has(msg.id)) {
        return;
    }

    exports.unread_topic_counter.delete(msg.id);

    exports.unread_topic_counter.add(
        new_stream_id || msg.stream_id,
        new_topic || msg.topic,
        msg.id,
    );
};

exports.process_loaded_messages = function (messages) {
    for (const message of messages) {
        if (!message.unread) {
            continue;
        }

        unread_messages.add(message.id);

        if (message.type === "private") {
            exports.unread_pm_counter.add(message);
        }

        if (message.type === "stream") {
            exports.unread_topic_counter.add(message.stream_id, message.topic, message.id);
        }

        exports.update_message_for_mention(message);
    }
};

exports.update_message_for_mention = function (message) {
    if (!message.unread) {
        exports.unread_mentions_counter.delete(message.id);
        return;
    }

    const is_unmuted_mention =
        message.type === "stream" &&
        message.mentioned &&
        !muting.is_topic_muted(message.stream_id, message.topic);

    if (is_unmuted_mention || message.mentioned_me_directly) {
        exports.unread_mentions_counter.add(message.id);
    } else {
        exports.unread_mentions_counter.delete(message.id);
    }
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

    const only_show_notifiable =
        page_params.desktop_icon_count_display ===
        settings_notifications.desktop_icon_count_display_values.notifiable.code;
    const no_notifications =
        page_params.desktop_icon_count_display ===
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

    for (const message_id of unread_msgs.mentions) {
        exports.unread_mentions_counter.add(message_id);
    }

    for (const obj of unread_msgs.huddles) {
        for (const message_id of obj.unread_message_ids) {
            unread_messages.add(message_id);
        }
    }

    for (const obj of unread_msgs.pms) {
        for (const message_id of obj.unread_message_ids) {
            unread_messages.add(message_id);
        }
    }

    for (const obj of unread_msgs.streams) {
        for (const message_id of obj.unread_message_ids) {
            unread_messages.add(message_id);
        }
    }

    for (const message_id of unread_msgs.mentions) {
        unread_messages.add(message_id);
    }
};

window.unread = exports;
