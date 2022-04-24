import {FoldDict} from "./fold_dict";
import * as message_store from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_config from "./settings_config";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import {user_settings} from "./user_settings";
import * as user_topics from "./user_topics";
import * as util from "./util";

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

export let messages_read_in_narrow = false;

export function set_messages_read_in_narrow(value) {
    messages_read_in_narrow = value;
}

export const unread_mentions_counter = new Set();
const unread_messages = new Set();

class Bucketer {
    // Maps item_id => bucket_key for items present in a bucket.
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
        this.reverse_lookup.set(item_id, bucket_key);
    }

    delete(item_id) {
        const bucket_key = this.reverse_lookup.get(item_id);
        if (bucket_key) {
            const bucket = this.get_bucket(bucket_key);
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
            const user_ids_string = obj.other_user_id.toString();
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

    add({message_id, user_ids_string}) {
        if (user_ids_string) {
            this.bucketer.add({
                bucket_key: user_ids_string,
                item_id: message_id,
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
const unread_pm_counter = new UnreadPMCounter();

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

            for (const message_id of unread_message_ids) {
                this.add({message_id, stream_id, topic});
            }
        }
    }

    add({message_id, stream_id, topic}) {
        this.bucketer.add({
            bucket_key: stream_id,
            item_id: message_id,
            add_callback(per_stream_bucketer) {
                per_stream_bucketer.add({
                    bucket_key: topic,
                    item_id: message_id,
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
            const sub = sub_store.get(stream_id);
            if (!sub || !stream_data.is_subscribed(stream_id)) {
                continue;
            }

            let stream_count = 0;
            for (const [topic, msgs] of per_stream_bucketer) {
                const topic_count = msgs.size;
                if (!user_topics.is_topic_muted(stream_id, topic)) {
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
        /* Clients have essentially complete unread data, but
         * stream_topic_history.is_complete_for_stream_id() can be
         * false. In that situation, this function helps ensure that
         * we include all topics with unread messages in data that.
         *
         * It will return all topics in the provided stream with a
         * nonzero unread count that are not already present in the
         * topic_dict parameter.
         */
        const stream_id = opts.stream_id;
        const topic_dict = opts.topic_dict;

        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);
        if (!per_stream_bucketer) {
            return [];
        }

        let topic_names = Array.from(per_stream_bucketer.keys());

        /* Include topics that have at least one unread. It would likely
         * be better design for buckets to be deleted when emptied. */
        topic_names = topic_names.filter((topic_name) => {
            const messages = Array.from(per_stream_bucketer.get_bucket(topic_name));
            return messages.length > 0;
        });
        /* And aren't already present in topic_dict. */
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

        const sub = sub_store.get(stream_id);
        for (const [topic, msgs] of per_stream_bucketer) {
            if (sub && !user_topics.is_topic_muted(stream_id, topic)) {
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
        const sub = sub_store.get(stream_id);
        for (const [topic, id_set] of per_stream_bucketer) {
            if (sub && !user_topics.is_topic_muted(stream_id, topic)) {
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

    get_streams_with_unread_mentions() {
        const streams_with_mentions = new Set();
        // Collect the set of streams containing at least one mention.
        // We can do this efficiently, since unread_mentions_counter
        // contains all unread message IDs, and we use stream_ids as
        // bucket keys in our outer bucketer.

        for (const message_id of unread_mentions_counter) {
            const stream_id = this.bucketer.reverse_lookup.get(message_id);
            streams_with_mentions.add(stream_id);
        }

        return streams_with_mentions;
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

    get_topics_with_unread_mentions(stream_id) {
        // Returns the set of lower cased topics with unread mentions
        // in the given stream.
        const result = new Set();
        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return result;
        }

        for (const message_id of unread_mentions_counter) {
            // Because bucket keys in per_stream_bucketer are topics,
            // we can just directly use reverse_lookup to find the
            // topic in this stream containing a given unread message
            // ID. If it's not in this stream, we'll get undefined.
            const topic_match = per_stream_bucketer.reverse_lookup.get(message_id);
            if (topic_match !== undefined) {
                // Important: We lower-case topics here before adding them
                // to this set, to support case-insensitive checks.
                result.add(topic_match.toLowerCase());
            }
        }

        return result;
    }
}
const unread_topic_counter = new UnreadTopicCounter();

export function message_unread(message) {
    if (message === undefined) {
        return false;
    }
    return message.unread;
}

export function get_read_message_ids(message_ids) {
    return message_ids.filter((message_id) => !unread_messages.has(message_id));
}

export function get_unread_message_ids(message_ids) {
    return message_ids.filter((message_id) => unread_messages.has(message_id));
}

export function get_unread_messages(messages) {
    return messages.filter((message) => unread_messages.has(message.id));
}

export function update_unread_topics(msg, event) {
    const new_topic = util.get_edit_event_topic(event);
    const {new_stream_id} = event;

    if (new_topic === undefined && new_stream_id === undefined) {
        return;
    }

    if (!unread_messages.has(msg.id)) {
        return;
    }

    unread_topic_counter.delete(msg.id);

    unread_topic_counter.add({
        message_id: msg.id,
        stream_id: new_stream_id || msg.stream_id,
        topic: new_topic || msg.topic,
    });
}

export function process_loaded_messages(messages) {
    for (const message of messages) {
        if (message.unread) {
            const user_ids_string =
                message.type === "private" ? people.pm_reply_user_string(message) : undefined;

            process_unread_message({
                id: message.id,
                mentioned: message.mentioned,
                mentioned_me_directly: message.mentioned_me_directly,
                stream_id: message.stream_id,
                topic: message.topic,
                type: message.type,
                unread: true,
                user_ids_string,
            });
        }
    }
}

export function process_unread_message(message) {
    // The `message` here just needs to require certain fields. For example,
    // the "message" may actually be constructed from a Zulip event that doesn't
    // include fields like "content".  The caller must verify that the message
    // is actually unread--we don't defend against that.
    unread_messages.add(message.id);

    if (message.type === "private") {
        unread_pm_counter.add({
            message_id: message.id,
            user_ids_string: message.user_ids_string,
        });
    }

    if (message.type === "stream") {
        unread_topic_counter.add({
            message_id: message.id,
            stream_id: message.stream_id,
            topic: message.topic,
        });
    }

    update_message_for_mention(message);
}

export function update_message_for_mention(message) {
    if (!message.unread) {
        unread_mentions_counter.delete(message.id);
        return;
    }

    const is_unmuted_mention =
        message.type === "stream" &&
        message.mentioned &&
        !user_topics.is_topic_muted(message.stream_id, message.topic);

    if (is_unmuted_mention || message.mentioned_me_directly) {
        unread_mentions_counter.add(message.id);
    } else {
        unread_mentions_counter.delete(message.id);
    }
}

export function mark_as_read(message_id) {
    // We don't need to check anything about the message, since all
    // the following methods are cheap and work fine even if message_id
    // was never set to unread.
    unread_pm_counter.delete(message_id);
    unread_topic_counter.delete(message_id);
    unread_mentions_counter.delete(message_id);
    unread_messages.delete(message_id);

    const message = message_store.get(message_id);
    if (message) {
        message.unread = false;
    }
}

export function declare_bankruptcy() {
    unread_pm_counter.clear();
    unread_topic_counter.clear();
    unread_mentions_counter.clear();
    unread_messages.clear();
}

export function get_counts() {
    const res = {};

    // Return a data structure with various counts.  This function should be
    // pretty cheap, even if you don't care about all the counts, and you
    // should strive to keep it free of side effects on globals or DOM.
    res.private_message_count = 0;
    res.mentioned_message_count = unread_mentions_counter.size;

    // This sets stream_count, topic_count, and home_unread_messages
    const topic_res = unread_topic_counter.get_counts();
    const streams_with_mentions = unread_topic_counter.get_streams_with_unread_mentions();
    res.home_unread_messages = topic_res.stream_unread_messages;
    res.stream_count = topic_res.stream_count;
    res.streams_with_mentions = Array.from(streams_with_mentions);

    const pm_res = unread_pm_counter.get_counts();
    res.pm_count = pm_res.pm_dict;
    res.private_message_count = pm_res.total_count;
    res.home_unread_messages += pm_res.total_count;

    return res;
}

// Saves us from calling to get_counts() when we can avoid it.
export function calculate_notifiable_count(res) {
    let new_message_count = 0;

    const only_show_notifiable =
        user_settings.desktop_icon_count_display ===
        settings_config.desktop_icon_count_display_values.notifiable.code;
    const no_notifications =
        user_settings.desktop_icon_count_display ===
        settings_config.desktop_icon_count_display_values.none.code;
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
}

export function get_notifiable_count() {
    const res = get_counts();
    return calculate_notifiable_count(res);
}

export function num_unread_for_stream(stream_id) {
    return unread_topic_counter.get_stream_count(stream_id);
}

export function num_unread_for_topic(stream_id, topic_name) {
    return unread_topic_counter.get(stream_id, topic_name);
}

export function stream_has_any_unread_mentions(stream_id) {
    const streams_with_mentions = unread_topic_counter.get_streams_with_unread_mentions();
    return streams_with_mentions.has(stream_id);
}

export function topic_has_any_unread(stream_id, topic) {
    return unread_topic_counter.topic_has_any_unread(stream_id, topic);
}

export function get_topics_with_unread_mentions(stream_id) {
    return unread_topic_counter.get_topics_with_unread_mentions(stream_id);
}

export function num_unread_for_person(user_ids_string) {
    return unread_pm_counter.num_unread(user_ids_string);
}

export function get_msg_ids_for_stream(stream_id) {
    return unread_topic_counter.get_msg_ids_for_stream(stream_id);
}

export function get_msg_ids_for_topic(stream_id, topic_name) {
    return unread_topic_counter.get_msg_ids_for_topic(stream_id, topic_name);
}

export function get_msg_ids_for_person(user_ids_string) {
    return unread_pm_counter.get_msg_ids_for_person(user_ids_string);
}

export function get_msg_ids_for_private() {
    return unread_pm_counter.get_msg_ids();
}

export function get_msg_ids_for_mentions() {
    const ids = Array.from(unread_mentions_counter);

    return util.sorted_ids(ids);
}

export function get_all_msg_ids() {
    const ids = Array.from(unread_messages);

    return util.sorted_ids(ids);
}

export function get_missing_topics(opts) {
    return unread_topic_counter.get_missing_topics(opts);
}

export function get_thread_unread_count_from_message(msg) {
    if (msg.type === "private") {
        return num_unread_for_person(msg.to_user_ids);
    }
    return num_unread_for_topic(msg.stream_id, msg.topic);
}

export function get_msg_ids_for_starred() {
    // This is here for API consistency sake--we never
    // have unread starred messages.  (Some day we may ironically
    // want to make starring the same as mark-as-unread, but
    // for now starring === reading.)
    return [];
}

export function initialize() {
    const unread_msgs = page_params.unread_msgs;

    unread_pm_counter.set_huddles(unread_msgs.huddles);
    unread_pm_counter.set_pms(unread_msgs.pms);
    unread_topic_counter.set_streams(unread_msgs.streams);

    for (const message_id of unread_msgs.mentions) {
        unread_mentions_counter.add(message_id);
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
}
