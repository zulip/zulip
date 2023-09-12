import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import * as message_store from "./message_store";
import * as people from "./people";
import * as recent_view_util from "./recent_view_util";
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

export let old_unreads_missing = false;

export function clear_old_unreads_missing() {
    old_unreads_missing = false;
}

export const unread_mentions_counter = new Set();
export const direct_message_with_mention_count = new Set();
const unread_messages = new Set();

// Map with keys of the form "{stream_id}:{topic.toLowerCase()}" and
// values being Sets of message IDs for unread messages mentioning the
// user within that topic. Use `recent_view_util.get_topic_key` to
// calculate keys.
//
// Functionally a cache; see clear_and_populate_unread_mention_topics
// for how we can refresh it efficiently.
export const unread_mention_topics = new Map();

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

class UnreadDirectMessageCounter {
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
        let right_sidebar_count = 0;
        for (const [user_ids_string, id_set] of this.bucketer) {
            const count = id_set.size;
            pm_dict.set(user_ids_string, count);
            const user_ids = people.user_ids_string_to_ids_array(user_ids_string);
            const is_with_one_human =
                user_ids.length === 1 && !people.get_by_user_id(user_ids[0]).is_bot;
            if (is_with_one_human) {
                right_sidebar_count += count;
            }
            total_count += count;
        }
        return {
            total_count,
            pm_dict,
            right_sidebar_count,
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

    get_msg_ids_for_user_ids_string(user_ids_string) {
        if (!user_ids_string) {
            return [];
        }

        const bucket = this.bucketer.get_bucket(user_ids_string);

        if (!bucket) {
            return [];
        }

        const ids = [...bucket];
        return util.sorted_ids(ids);
    }
}
const unread_direct_message_counter = new UnreadDirectMessageCounter();

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

    get_counts(include_per_topic_count = false) {
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

            if (include_per_topic_count) {
                const topic_unread = new Map();
                let stream_count = 0;
                for (const [topic, msgs] of per_stream_bucketer) {
                    const topic_count = msgs.size;
                    topic_unread.set(topic, topic_count);
                    stream_count += topic_count;
                }

                // Note: The format of res.stream_count is completely
                // different from the else clause; with objects
                // containing data for individual topics rather than
                // just muted/unmuted totals, and all muted
                // streams/topics included so that the inbox view can
                // easily show/hide topics when its filters are
                // adjusted.  This should be refactored before the
                // TypeScript migration for this file.
                res.stream_count.set(stream_id, topic_unread);
                res.stream_unread_messages += stream_count;
            } else {
                // get_stream_count calculates both the number of
                // unmuted unread as well as the number of muted
                // unreads.
                res.stream_count.set(stream_id, this.get_stream_count(stream_id));
                res.stream_unread_messages += res.stream_count.get(stream_id).unmuted_count;
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

        let topic_names = [...per_stream_bucketer.keys()];

        /* Include topics that have at least one unread. It would likely
         * be better design for buckets to be deleted when emptied. */
        topic_names = topic_names.filter((topic_name) => {
            const messages = [...per_stream_bucketer.get_bucket(topic_name)];
            return messages.length > 0;
        });
        /* And aren't already present in topic_dict. */
        topic_names = topic_names.filter((topic_name) => !topic_dict.has(topic_name));

        const result = topic_names.map((topic_name) => {
            const msgs = per_stream_bucketer.get_bucket(topic_name);

            return {
                pretty_name: topic_name,
                message_id: Math.max(...msgs),
            };
        });

        return result;
    }

    get_stream_count(stream_id) {
        const per_stream_bucketer = this.bucketer.get_bucket(stream_id);

        if (!per_stream_bucketer) {
            return 0;
        }

        const sub = sub_store.get(stream_id);
        let unmuted_count = 0;
        let muted_count = 0;
        for (const [topic, msgs] of per_stream_bucketer) {
            const topic_count = msgs.size;

            if (user_topics.is_topic_unmuted(stream_id, topic)) {
                unmuted_count += topic_count;
            } else if (user_topics.is_topic_muted(stream_id, topic)) {
                muted_count += topic_count;
            } else if (sub.is_muted) {
                muted_count += topic_count;
            } else {
                unmuted_count += topic_count;
            }
        }
        const stream_count = {
            unmuted_count,
            muted_count,
            stream_is_muted: sub.is_muted,
        };
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

        const ids = [...topic_bucket];
        return util.sorted_ids(ids);
    }

    get_streams_with_unread_mentions() {
        // Collect the set of streams containing at least one unread
        // mention, without considering muting.

        // We can do this efficiently, since unread_mentions_counter
        // contains all unread message IDs, and we use stream_ids as
        // bucket keys in our outer bucketer.
        const streams_with_mentions = new Set();

        for (const message_id of unread_mentions_counter) {
            const stream_id = this.bucketer.reverse_lookup.get(message_id);
            if (stream_id === undefined) {
                // This is a direct message containing a mention.
                continue;
            }
            streams_with_mentions.add(stream_id);
        }

        return streams_with_mentions;
    }

    get_streams_with_unmuted_mentions() {
        // Collect the set of streams containing at least one mention
        // that is not in a muted topic or non-unmuted topic in a
        // muted stream.
        const streams_with_unmuted_mentions = new Set();
        for (const message_id of unread_mentions_counter) {
            const stream_id = this.bucketer.reverse_lookup.get(message_id);
            if (stream_id === undefined) {
                // This is a direct message containing a mention.
                continue;
            }

            const stream_bucketer = this.bucketer.get_bucket(stream_id);
            const topic = stream_bucketer.reverse_lookup.get(message_id);
            const stream_is_muted = sub_store.get(stream_id)?.is_muted;
            if (stream_is_muted) {
                if (user_topics.is_topic_unmuted(stream_id, topic)) {
                    streams_with_unmuted_mentions.add(stream_id);
                }
            } else {
                if (!user_topics.is_topic_muted(stream_id, topic)) {
                    streams_with_unmuted_mentions.add(stream_id);
                }
            }
        }
        return streams_with_unmuted_mentions;
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

function add_message_to_unread_mention_topics(message_id) {
    const message = message_store.get(message_id);
    if (message.type !== "stream") {
        return;
    }
    const topic_key = recent_view_util.get_topic_key(message.stream_id, message.topic);
    if (unread_mention_topics.has(topic_key)) {
        unread_mention_topics.get(topic_key).add(message_id);
    }
    unread_mention_topics.set(topic_key, new Set([message_id]));
}

function remove_message_from_unread_mention_topics(message_id) {
    const stream_id = unread_topic_counter.bucketer.reverse_lookup.get(message_id);
    if (!stream_id) {
        // Direct messages and messages that were already not unread
        // exit here.
        return;
    }

    const per_stream_bucketer = unread_topic_counter.bucketer.get_bucket(stream_id);
    if (!per_stream_bucketer) {
        blueslip.error("Could not find per_stream_bucketer", {message_id});
        return;
    }

    const topic = per_stream_bucketer.reverse_lookup.get(message_id);
    const topic_key = recent_view_util.get_topic_key(stream_id, topic);
    if (unread_mention_topics.has(topic_key)) {
        unread_mention_topics.get(topic_key).delete(message_id);
    }
}

export function clear_and_populate_unread_mention_topics() {
    // The unread_mention_topics is an important data structure for
    // efficiently querying whether a given stream/topic pair contains
    // unread mentions.
    //
    // It is effectively a cache, since it can be reconstructed from
    // unread_mentions_counter (IDs for all unread mentions) and
    // unread_topic_counter (Streams/topics for all unread messages).
    //
    // Since this function runs in O(unread mentions) time, we can use
    // it in topic editing code paths where it might be onerous to
    // write custom live-update code; but we should avoid calling it
    // in loops.
    unread_mention_topics.clear();

    for (const message_id of unread_mentions_counter) {
        const stream_id = unread_topic_counter.bucketer.reverse_lookup.get(message_id);
        if (!stream_id) {
            continue;
        }
        const per_stream_bucketer = unread_topic_counter.bucketer.get_bucket(stream_id);
        const topic = per_stream_bucketer.reverse_lookup.get(message_id);
        const topic_key = recent_view_util.get_topic_key(stream_id, topic);
        if (unread_mention_topics.has(topic_key)) {
            unread_mention_topics.get(topic_key).add(message_id);
        }
        unread_mention_topics.set(topic_key, new Set([message_id]));
    }
}

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

export function get_unread_message_count() {
    return unread_messages.size;
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

export function process_loaded_messages(messages, expect_no_new_unreads = false) {
    // Process a set of messages that we have full copies of from the
    // server for whether any are unread but not tracked as such by
    // our data structures. This can occur due to old_unreads_missing,
    // changes in muting configuration, innocent races, or potentially bugs.
    //
    // Returns whether there were any new unread messages; in that
    // case, the caller will need to trigger a rerender of UI
    // displaying unread counts.

    let any_untracked_unread_messages = false;
    for (const message of messages) {
        if (message.unread) {
            if (unread_messages.has(message.id)) {
                // If we're already tracking this message as unread, there's nothing to do.
                continue;
            }

            if (expect_no_new_unreads && !old_unreads_missing) {
                // This may happen due to races, where someone narrows
                // to a view and the message_fetch request returns
                // before server_events system delivers the message to
                // the client.
                blueslip.log(`New unread ${message.id} discovered in process_loaded_messages.`);
            }

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
            any_untracked_unread_messages = true;
        }
    }

    return any_untracked_unread_messages;
}

export function process_unread_message(message) {
    // The `message` here just needs to require certain fields. For example,
    // the "message" may actually be constructed from a Zulip event that doesn't
    // include fields like "content".  The caller must verify that the message
    // is actually unread--we don't defend against that.
    unread_messages.add(message.id);

    if (message.type === "private") {
        unread_direct_message_counter.add({
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

export function update_message_for_mention(message, content_edited = false) {
    // Returns true if this is a stream message whose content was
    // changed, and thus the caller might need to trigger a rerender
    // of UI elements displaying whether the message's topic contains
    // an unread mention of the user.
    if (!message.unread) {
        unread_mentions_counter.delete(message.id);
        direct_message_with_mention_count.delete(message.id);
        remove_message_from_unread_mention_topics(message.id);
        return false;
    }

    const is_unmuted_mention =
        message.type === "stream" &&
        message.mentioned &&
        !user_topics.is_topic_muted(message.stream_id, message.topic);

    if (is_unmuted_mention || message.mentioned_me_directly) {
        unread_mentions_counter.add(message.id);
        add_message_to_unread_mention_topics(message.id);
        if (!message.stream_id) {
            direct_message_with_mention_count.add(message.id);
        }
    } else {
        unread_mentions_counter.delete(message.id);
        direct_message_with_mention_count.delete(message.id);
        remove_message_from_unread_mention_topics(message.id);
    }

    if (content_edited && message.type === "stream") {
        return true;
    }
    return false;
}

export function mark_as_read(message_id) {
    // We don't need to check anything about the message, since all
    // the following methods are cheap and work fine even if message_id
    // was never set to unread.
    unread_direct_message_counter.delete(message_id);

    // Important: This function uses `unread_topic_counter` to look up
    // the stream/topic for this previously unread message, so much
    // happen before the message is removed from that data structure.
    remove_message_from_unread_mention_topics(message_id);
    unread_topic_counter.delete(message_id);
    unread_mentions_counter.delete(message_id);
    direct_message_with_mention_count.delete(message_id);
    unread_messages.delete(message_id);

    const message = message_store.get(message_id);
    if (message) {
        message.unread = false;
    }
}

export function declare_bankruptcy() {
    // Only used in tests.
    unread_direct_message_counter.clear();
    unread_topic_counter.clear();
    unread_mentions_counter.clear();
    direct_message_with_mention_count.clear();
    unread_messages.clear();
    unread_mention_topics.clear();
}

export function get_unread_pm() {
    const pm_res = unread_direct_message_counter.get_counts();
    return pm_res;
}

export function get_unread_topics() {
    const include_per_topic_count = true;
    const topics_res = unread_topic_counter.get_counts(include_per_topic_count);
    return topics_res;
}

export function get_counts() {
    const res = {};

    // Return a data structure with various counts.  This function should be
    // pretty cheap, even if you don't care about all the counts, and you
    // should strive to keep it free of side effects on globals or DOM.
    res.direct_message_count = 0;
    res.mentioned_message_count = unread_mentions_counter.size;
    res.direct_message_with_mention_count = direct_message_with_mention_count.size;

    // This sets stream_count, topic_count, and home_unread_messages
    const topic_res = unread_topic_counter.get_counts();
    const streams_with_mentions = unread_topic_counter.get_streams_with_unread_mentions();
    const streams_with_unmuted_mentions = unread_topic_counter.get_streams_with_unmuted_mentions();
    res.home_unread_messages = topic_res.stream_unread_messages;
    res.stream_count = topic_res.stream_count;
    res.streams_with_mentions = [...streams_with_mentions];
    res.streams_with_unmuted_mentions = [...streams_with_unmuted_mentions];

    const pm_res = unread_direct_message_counter.get_counts();
    res.pm_count = pm_res.pm_dict;
    res.direct_message_count = pm_res.total_count;
    res.right_sidebar_direct_message_count = pm_res.right_sidebar_count;
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
        new_message_count =
            res.mentioned_message_count +
            res.direct_message_count -
            // Avoid double-counting direct messages containing mentions
            res.direct_message_with_mention_count;
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
    // This function is somewhat inefficient and thus should not be
    // called in loops, since runs in O(total unread mentions) time.
    const streams_with_mentions = unread_topic_counter.get_streams_with_unread_mentions();
    return streams_with_mentions.has(stream_id);
}

export function stream_has_any_unmuted_mentions(stream_id) {
    // This function is somewhat inefficient and thus should not be
    // called in loops, since runs in O(total unread mentions) time.
    const streams_with_mentions = unread_topic_counter.get_streams_with_unmuted_mentions();
    return streams_with_mentions.has(stream_id);
}

export function topic_has_any_unread_mentions(stream_id, topic) {
    // Because this function is called in a loop for every displayed
    // Recent Conversations row, it's important for it to run in O(1) time.
    const topic_key = stream_id + ":" + topic.toLowerCase();
    return unread_mention_topics.get(topic_key) && unread_mention_topics.get(topic_key).size > 0;
}

export function topic_has_any_unread(stream_id, topic) {
    return unread_topic_counter.topic_has_any_unread(stream_id, topic);
}

export function get_topics_with_unread_mentions(stream_id) {
    return unread_topic_counter.get_topics_with_unread_mentions(stream_id);
}

export function num_unread_for_user_ids_string(user_ids_string) {
    return unread_direct_message_counter.num_unread(user_ids_string);
}

export function get_msg_ids_for_stream(stream_id) {
    return unread_topic_counter.get_msg_ids_for_stream(stream_id);
}

export function get_msg_ids_for_topic(stream_id, topic_name) {
    return unread_topic_counter.get_msg_ids_for_topic(stream_id, topic_name);
}

export function get_msg_ids_for_user_ids_string(user_ids_string) {
    return unread_direct_message_counter.get_msg_ids_for_user_ids_string(user_ids_string);
}

export function get_msg_ids_for_private() {
    return unread_direct_message_counter.get_msg_ids();
}

export function get_msg_ids_for_mentions() {
    const ids = [...unread_mentions_counter];

    return util.sorted_ids(ids);
}

export function get_all_msg_ids() {
    const ids = [...unread_messages];

    return util.sorted_ids(ids);
}

export function get_missing_topics(opts) {
    return unread_topic_counter.get_missing_topics(opts);
}

export function get_msg_ids_for_starred() {
    // This is here for API consistency sake--we never
    // have unread starred messages.  (Some day we may ironically
    // want to make starring the same as mark-as-unread, but
    // for now starring === reading.)
    return [];
}

export function initialize(params) {
    const unread_msgs = params.unread_msgs;

    old_unreads_missing = unread_msgs.old_unreads_missing;
    unread_direct_message_counter.set_huddles(unread_msgs.huddles);
    unread_direct_message_counter.set_pms(unread_msgs.pms);
    unread_topic_counter.set_streams(unread_msgs.streams);
    for (const message_id of unread_msgs.mentions) {
        unread_mentions_counter.add(message_id);
        if (unread_direct_message_counter.get_msg_ids().includes(message_id)) {
            direct_message_with_mention_count.add(message_id);
        }
    }
    clear_and_populate_unread_mention_topics();

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
