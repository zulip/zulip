import * as blueslip from "./blueslip";
import {FoldDict} from "./fold_dict";
import * as message_store from "./message_store";
import type {Message} from "./message_store";
import * as people from "./people";
import * as recent_view_util from "./recent_view_util";
import * as settings_config from "./settings_config";
import * as stream_data from "./stream_data";
import type {TopicHistoryEntry} from "./stream_topic_history";
import * as sub_store from "./sub_store";
import type {UpdateMessageEvent} from "./types";
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

export let old_unreads_missing = false;

export function clear_old_unreads_missing(): void {
    old_unreads_missing = false;
}

export const unread_mentions_counter = new Set<number>();
export const direct_message_with_mention_count = new Set();
const unread_messages = new Set<number>();

// Map with keys of the form "{stream_id}:{topic.toLowerCase()}" and
// values being Sets of message IDs for unread messages mentioning the
// user within that topic. Use `recent_view_util.get_topic_key` to
// calculate keys.
//
// Functionally a cache; see clear_and_populate_unread_mention_topics
// for how we can refresh it efficiently.
export const unread_mention_topics = new Map<string, Set<number>>();

export type StreamCountInfo = {
    unmuted_count: number;
    muted_count: number;
    followed_count: number;
    stream_is_muted: boolean;
};

type DirectMessageCountInfo = {
    total_count: number;
    pm_dict: Map<string, number>;
};

type DirectMessageCountInfoWithLatestMsgId = {
    total_count: number;
    pm_dict: Map<string, {count: number; latest_msg_id: number}>;
};

class UnreadDirectMessageCounter {
    bucketer = new Map<string, Set<number>>();
    // Maps direct message id to the user id string that's the key for bucketer
    reverse_lookup = new Map<number, string>();

    clear(): void {
        this.bucketer.clear();
        this.reverse_lookup.clear();
    }

    set_pms(pms: UnreadDirectMessageInfo[]): void {
        for (const obj of pms) {
            const user_ids_string = obj.other_user_id.toString();
            this.set_message_ids(user_ids_string, obj.unread_message_ids);
        }
    }

    set_huddles(huddles: UnreadHuddleInfo[]): void {
        for (const obj of huddles) {
            const user_ids_string = people.pm_lookup_key(obj.user_ids_string);
            this.set_message_ids(user_ids_string, obj.unread_message_ids);
        }
    }

    set_message_ids(user_ids_string: string, unread_message_ids: number[]): void {
        for (const message_id of unread_message_ids) {
            this.add({message_id, user_ids_string});
        }
    }

    add({message_id, user_ids_string}: {message_id: number; user_ids_string: string}): void {
        if (user_ids_string) {
            let bucket = this.bucketer.get(user_ids_string);
            if (bucket === undefined) {
                bucket = new Set();
                this.bucketer.set(user_ids_string, bucket);
            }
            bucket.add(message_id);
            this.reverse_lookup.set(message_id, user_ids_string);
        }
    }

    delete(message_id: number): void {
        const user_ids_string = this.reverse_lookup.get(message_id);
        if (user_ids_string === undefined) {
            return;
        }
        this.bucketer.get(user_ids_string)?.delete(message_id);
        this.reverse_lookup.delete(message_id);
    }

    get_counts(): DirectMessageCountInfo {
        const pm_dict = new Map<string, number>(); // Hash by user_ids_string -> count Optional[, max_id]
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

    get_counts_with_latest_msg_id(): DirectMessageCountInfoWithLatestMsgId {
        const pm_dict = new Map<string, {count: number; latest_msg_id: number}>(); // Hash by user_ids_string -> count Optional[, max_id]
        let total_count = 0;
        for (const [user_ids_string, id_set] of this.bucketer) {
            const count = id_set.size;
            const latest_msg_id = Math.max(...id_set);
            pm_dict.set(user_ids_string, {
                count,
                latest_msg_id,
            });
            total_count += count;
        }
        return {
            total_count,
            pm_dict,
        };
    }

    num_unread(user_ids_string: string): number {
        if (!user_ids_string) {
            return 0;
        }

        const bucket = this.bucketer.get(user_ids_string);

        if (!bucket) {
            return 0;
        }
        return bucket.size;
    }

    get_msg_ids(): number[] {
        const ids = [];

        for (const id_set of this.bucketer.values()) {
            for (const id of id_set) {
                ids.push(id);
            }
        }

        return util.sorted_ids(ids);
    }

    get_msg_ids_for_user_ids_string(user_ids_string: string): number[] {
        if (!user_ids_string) {
            return [];
        }

        const bucket = this.bucketer.get(user_ids_string);

        if (!bucket) {
            return [];
        }

        const ids = [...bucket];
        return util.sorted_ids(ids);
    }
}
const unread_direct_message_counter = new UnreadDirectMessageCounter();

type UnreadStreamCounts = {
    stream_unread_messages: number;
    followed_topic_unread_messages: number;
    stream_count: Map<number, StreamCountInfo>;
};

type UnreadTopicCounts = {
    stream_unread_messages: number;
    // stream_id -> topic_name -> topic counts
    topic_counts: Map<
        number,
        Map<
            string,
            {
                topic_count: number;
                latest_msg_id: number;
            }
        >
    >;
};

class UnreadTopicCounter {
    bucketer = new Map<number, FoldDict<Set<number>>>();
    // Maps the message id to the (stream, topic) we stored it under in the bucketer.
    reverse_lookup = new Map<number, {stream_id: number; topic: string}>();

    clear(): void {
        this.bucketer.clear();
        this.reverse_lookup.clear();
    }

    set_streams(objs: {stream_id: number; topic: string; unread_message_ids: number[]}[]): void {
        for (const obj of objs) {
            const stream_id = obj.stream_id;
            const topic = obj.topic;
            const unread_message_ids = obj.unread_message_ids;

            for (const message_id of unread_message_ids) {
                this.add({message_id, stream_id, topic});
            }
        }
    }

    add({
        message_id,
        stream_id,
        topic,
    }: {
        message_id: number;
        stream_id: number;
        topic: string;
    }): void {
        let per_stream_bucketer = this.bucketer.get(stream_id);
        if (per_stream_bucketer === undefined) {
            per_stream_bucketer = new FoldDict();
            this.bucketer.set(stream_id, per_stream_bucketer);
        }
        let bucket = per_stream_bucketer.get(topic);
        if (bucket === undefined) {
            bucket = new Set();
            per_stream_bucketer.set(topic, bucket);
        }
        this.reverse_lookup.set(message_id, {stream_id, topic});
        bucket.add(message_id);
    }

    delete(message_id: number): void {
        const stream_topic = this.reverse_lookup.get(message_id);
        if (stream_topic === undefined) {
            return;
        }
        const {stream_id, topic} = stream_topic;
        this.bucketer.get(stream_id)?.get(topic)?.delete(message_id);
        this.reverse_lookup.delete(message_id);
    }

    get_counts_per_topic(): UnreadTopicCounts {
        let stream_unread_messages = 0;
        const topic_counts_by_stream_id = new Map<
            number,
            Map<string, {topic_count: number; latest_msg_id: number}>
        >(); // hash by stream_id -> count
        for (const [stream_id, per_stream_bucketer] of this.bucketer) {
            // We track unread counts for streams that may be currently
            // unsubscribed.  Since users may re-subscribe, we don't
            // completely throw away the data.  But we do ignore it here,
            // so that callers have a view of the **current** world.
            const sub = sub_store.get(stream_id);
            if (!sub || !stream_data.is_subscribed(stream_id)) {
                continue;
            }

            const topic_unread = new Map<string, {topic_count: number; latest_msg_id: number}>();
            let stream_count = 0;
            for (const [topic, msgs] of per_stream_bucketer) {
                const topic_count = msgs.size;
                const latest_msg_id = Math.max(...msgs);
                topic_unread.set(topic, {
                    topic_count,
                    latest_msg_id,
                });
                stream_count += topic_count;
            }

            topic_counts_by_stream_id.set(stream_id, topic_unread);
            stream_unread_messages += stream_count;
        }

        return {
            stream_unread_messages,
            topic_counts: topic_counts_by_stream_id,
        };
    }

    get_counts(): UnreadStreamCounts {
        let stream_unread_messages = 0;
        let followed_topic_unread_messages = 0;
        const stream_counts_by_id = new Map<number, StreamCountInfo>(); // hash by stream_id -> count
        for (const stream_id of this.bucketer.keys()) {
            // We track unread counts for streams that may be currently
            // unsubscribed.  Since users may re-subscribe, we don't
            // completely throw away the data.  But we do ignore it here,
            // so that callers have a view of the **current** world.
            const sub = sub_store.get(stream_id);
            if (!sub || !stream_data.is_subscribed(stream_id)) {
                continue;
            }

            // get_stream_count_info calculates both the number of
            // unmuted unread as well as the number of muted
            // unreads.
            const stream_count_info = this.get_stream_count_info(stream_id);
            stream_counts_by_id.set(stream_id, stream_count_info);
            stream_unread_messages += stream_count_info.unmuted_count;
            followed_topic_unread_messages += stream_count_info.followed_count;
        }

        return {
            stream_unread_messages,
            followed_topic_unread_messages,
            stream_count: stream_counts_by_id,
        };
    }

    get_missing_topics(opts: {
        stream_id: number;
        topic_dict: FoldDict<TopicHistoryEntry>;
    }): {pretty_name: string; message_id: number}[] {
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

        const per_stream_bucketer = this.bucketer.get(stream_id);
        if (!per_stream_bucketer) {
            return [];
        }

        let topics_and_message_ids = [...per_stream_bucketer];

        /* Include topics that have at least one unread. It would likely
         * be better design for buckets to be deleted when emptied. */
        topics_and_message_ids = topics_and_message_ids.filter(
            ([_, message_ids]) => message_ids.size > 0,
        );
        /* And aren't already present in topic_dict. */
        topics_and_message_ids = topics_and_message_ids.filter(
            ([topic_name, _]) => !topic_dict.has(topic_name),
        );

        const result = topics_and_message_ids.map(([topic_name, message_ids]) => ({
            pretty_name: topic_name,
            message_id: Math.max(...message_ids),
        }));

        return result;
    }

    get_stream_count_info(stream_id: number): StreamCountInfo {
        const per_stream_bucketer = this.bucketer.get(stream_id);

        if (!per_stream_bucketer) {
            return {
                unmuted_count: 0,
                muted_count: 0,
                followed_count: 0,
                stream_is_muted: false,
            };
        }

        const sub = sub_store.get(stream_id);
        let unmuted_count = 0;
        let muted_count = 0;
        let followed_count = 0;
        for (const [topic, msgs] of per_stream_bucketer) {
            const topic_count = msgs.size;

            if (user_topics.is_topic_followed(stream_id, topic)) {
                followed_count += topic_count;
            }

            if (user_topics.is_topic_unmuted_or_followed(stream_id, topic)) {
                unmuted_count += topic_count;
            } else if (user_topics.is_topic_muted(stream_id, topic)) {
                muted_count += topic_count;
            } else if (sub?.is_muted) {
                muted_count += topic_count;
            } else {
                unmuted_count += topic_count;
            }
        }
        const stream_count = {
            unmuted_count,
            muted_count,
            followed_count,
            stream_is_muted: sub?.is_muted ?? false,
        };
        return stream_count;
    }

    get(stream_id: number, topic: string): number {
        const per_stream_bucketer = this.bucketer.get(stream_id);
        if (!per_stream_bucketer) {
            return 0;
        }

        const topic_bucket = per_stream_bucketer.get(topic);
        if (!topic_bucket) {
            return 0;
        }

        return topic_bucket.size;
    }

    get_msg_ids_for_stream(stream_id: number): number[] {
        const per_stream_bucketer = this.bucketer.get(stream_id);

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

    get_msg_ids_for_topic(stream_id: number, topic: string): number[] {
        const per_stream_bucketer = this.bucketer.get(stream_id);
        if (!per_stream_bucketer) {
            return [];
        }

        const topic_bucket = per_stream_bucketer.get(topic);
        if (!topic_bucket) {
            return [];
        }

        const ids = [...topic_bucket];
        return util.sorted_ids(ids);
    }

    get_streams_with_unread_mentions(): Set<number> {
        // Collect the set of streams containing at least one unread
        // mention, without considering muting.

        // We can do this efficiently, since unread_mentions_counter
        // contains all unread message IDs, and we use stream_ids as
        // bucket keys in our outer bucketer.
        const streams_with_mentions = new Set<number>();

        for (const message_id of unread_mentions_counter) {
            const stream_id = this.reverse_lookup.get(message_id)?.stream_id;
            if (stream_id === undefined) {
                // This is a direct message containing a mention.
                continue;
            }
            streams_with_mentions.add(stream_id);
        }

        return streams_with_mentions;
    }

    get_streams_with_unmuted_mentions(): Set<number> {
        // Collect the set of streams containing at least one mention
        // that is not in a muted topic or non-unmuted topic in a
        // muted stream.
        const streams_with_unmuted_mentions = new Set<number>();
        for (const message_id of unread_mentions_counter) {
            const stream_topic = this.reverse_lookup.get(message_id);
            if (stream_topic === undefined) {
                // This is a direct message containing a mention.
                continue;
            }
            const {stream_id, topic} = stream_topic;

            const stream_is_muted = sub_store.get(stream_id)?.is_muted;
            if (stream_is_muted) {
                if (user_topics.is_topic_unmuted_or_followed(stream_id, topic)) {
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

    get_followed_topic_unread_mentions(): number {
        let followed_topic_unread_mentions = 0;
        for (const message_id of unread_mentions_counter) {
            const stream_topic = this.reverse_lookup.get(message_id);
            if (stream_topic === undefined) {
                // This is a direct message containing a mention.
                continue;
            }
            const {stream_id, topic} = stream_topic;

            if (user_topics.is_topic_followed(stream_id, topic)) {
                followed_topic_unread_mentions += 1;
            }
        }
        return followed_topic_unread_mentions;
    }

    topic_has_any_unread(stream_id: number, topic: string): boolean {
        const per_stream_bucketer = this.bucketer.get(stream_id);

        if (!per_stream_bucketer) {
            return false;
        }

        const id_set = per_stream_bucketer.get(topic);
        if (!id_set) {
            return false;
        }

        return id_set.size !== 0;
    }

    get_topics_with_unread_mentions(stream_id: number): Set<string> {
        // Returns the set of lower cased topics with unread mentions
        // in the given stream.
        const result = new Set<string>();
        const per_stream_bucketer = this.bucketer.get(stream_id);

        if (!per_stream_bucketer) {
            return result;
        }

        for (const message_id of unread_mentions_counter) {
            // Because bucket keys in per_stream_bucketer are topics,
            // we can just directly use reverse_lookup to find the
            // topic in this stream containing a given unread message
            // ID. If it's not in this stream, we'll get undefined.
            const stream_topic = this.reverse_lookup.get(message_id);
            if (stream_topic !== undefined && stream_topic.stream_id === stream_id) {
                // Important: We lower-case topics here before adding them
                // to this set, to support case-insensitive checks.
                result.add(stream_topic.topic.toLowerCase());
            }
        }

        return result;
    }
}
const unread_topic_counter = new UnreadTopicCounter();

function add_message_to_unread_mention_topics(message_id: number): void {
    const message = message_store.get(message_id);
    if (message?.type !== "stream") {
        return;
    }
    const topic_key = recent_view_util.get_topic_key(message.stream_id, message.topic);
    const topic_message_ids = unread_mention_topics.get(topic_key);
    if (topic_message_ids !== undefined) {
        topic_message_ids.add(message_id);
    } else {
        unread_mention_topics.set(topic_key, new Set([message_id]));
    }
}

function remove_message_from_unread_mention_topics(message_id: number): void {
    const stream_topic = unread_topic_counter.reverse_lookup.get(message_id);
    if (!stream_topic) {
        // Direct messages and messages that were already not unread
        // exit here.
        return;
    }
    const {stream_id, topic} = stream_topic;
    const topic_key = recent_view_util.get_topic_key(stream_id, topic);
    unread_mention_topics.get(topic_key)?.delete(message_id);
}

export function clear_and_populate_unread_mention_topics(): void {
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
        const stream_topic = unread_topic_counter.reverse_lookup.get(message_id);
        if (!stream_topic) {
            // Direct messages and messages that were already not unread
            // exit here.
            continue;
        }
        const {stream_id, topic} = stream_topic;

        const topic_key = recent_view_util.get_topic_key(stream_id, topic);
        const topic_message_ids = unread_mention_topics.get(topic_key);
        if (topic_message_ids !== undefined) {
            topic_message_ids.add(message_id);
        } else {
            unread_mention_topics.set(topic_key, new Set([message_id]));
        }
    }
}

export function message_unread(message: Message): boolean {
    if (message === undefined) {
        return false;
    }
    return message.unread;
}

export function get_read_message_ids(message_ids: number[]): number[] {
    return message_ids.filter((message_id) => !unread_messages.has(message_id));
}

export function get_unread_message_ids(message_ids: number[]): number[] {
    return message_ids.filter((message_id) => unread_messages.has(message_id));
}

export function get_unread_messages(messages: Message[]): Message[] {
    return messages.filter((message) => unread_messages.has(message.id));
}

export function get_unread_message_count(): number {
    return unread_messages.size;
}

export function update_unread_topics(
    msg: Message & {type: "stream"},
    event: UpdateMessageEvent,
): void {
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
        stream_id: new_stream_id ?? msg.stream_id,
        topic: new_topic ?? msg.topic,
    });
}

export function process_loaded_messages(
    messages: Message[],
    expect_no_new_unreads = false,
): boolean {
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

            if (message.type === "private") {
                process_unread_message({
                    id: message.id,
                    mentioned: message.mentioned,
                    mentioned_me_directly: message.mentioned_me_directly,
                    type: message.type,
                    user_ids_string: people.pm_reply_user_string(message) ?? "",
                    unread: true,
                });
            } else {
                process_unread_message({
                    id: message.id,
                    mentioned: message.mentioned,
                    mentioned_me_directly: message.mentioned_me_directly,
                    type: message.type,
                    stream_id: message.stream_id,
                    topic: message.topic,
                    unread: true,
                });
            }
            any_untracked_unread_messages = true;
        }
    }

    return any_untracked_unread_messages;
}

type UnreadMessageData = {
    id: number;
    mentioned: boolean;
    mentioned_me_directly: boolean;
    unread: boolean;
} & (
    | {
          type: "private";
          user_ids_string: string;
      }
    | {
          type: "stream";
          stream_id: number;
          topic: string;
      }
);

export function process_unread_message(message: UnreadMessageData): void {
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

export function update_message_for_mention(
    message: UnreadMessageData,
    content_edited = false,
): boolean {
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

    // A message is said to have an unmuted mention if message contains a mention and
    // if the message is a direct message or
    // if the message is in a non muted topic in an unmuted stream or
    // if the message is in a followed or an unmuted topic in a muted stream.
    const is_unmuted_mention =
        message.mentioned &&
        (message.type === "private" ||
            (!stream_data.is_muted(message.stream_id) &&
                !user_topics.is_topic_muted(message.stream_id, message.topic)) ||
            (stream_data.is_muted(message.stream_id) &&
                user_topics.is_topic_unmuted_or_followed(message.stream_id, message.topic)));

    if (is_unmuted_mention || message.mentioned_me_directly) {
        unread_mentions_counter.add(message.id);
        add_message_to_unread_mention_topics(message.id);
        if (message.type === "private") {
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

export function mark_as_read(message_id: number): void {
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

export function declare_bankruptcy(): void {
    // Only used in tests.
    unread_direct_message_counter.clear();
    unread_topic_counter.clear();
    unread_mentions_counter.clear();
    direct_message_with_mention_count.clear();
    unread_messages.clear();
    unread_mention_topics.clear();
}

export function get_unread_pm(): DirectMessageCountInfoWithLatestMsgId {
    return unread_direct_message_counter.get_counts_with_latest_msg_id();
}

export function get_unread_topics(): UnreadTopicCounts {
    return unread_topic_counter.get_counts_per_topic();
}

export type FullUnreadCountsData = {
    direct_message_count: number;
    mentioned_message_count: number;
    direct_message_with_mention_count: number;
    stream_unread_messages: number;
    followed_topic_unread_messages_count: number;
    followed_topic_unread_messages_with_mention_count: number;
    stream_count: Map<number, StreamCountInfo>;
    streams_with_mentions: number[];
    streams_with_unmuted_mentions: number[];
    pm_count: Map<string, number>;
    home_unread_messages: number;
};

// Return a data structure with various counts.  This function should be
// pretty cheap, even if you don't care about all the counts, and you
// should strive to keep it free of side effects on globals or DOM.
export function get_counts(): FullUnreadCountsData {
    const topic_res = unread_topic_counter.get_counts();
    const pm_res = unread_direct_message_counter.get_counts();

    return {
        direct_message_count: pm_res.total_count,
        mentioned_message_count: unread_mentions_counter.size,
        direct_message_with_mention_count: direct_message_with_mention_count.size,
        stream_unread_messages: topic_res.stream_unread_messages,
        followed_topic_unread_messages_count: topic_res.followed_topic_unread_messages,
        followed_topic_unread_messages_with_mention_count:
            unread_topic_counter.get_followed_topic_unread_mentions(),
        stream_count: topic_res.stream_count,
        streams_with_mentions: [...unread_topic_counter.get_streams_with_unread_mentions()],
        streams_with_unmuted_mentions: [
            ...unread_topic_counter.get_streams_with_unmuted_mentions(),
        ],
        pm_count: pm_res.pm_dict,
        home_unread_messages: topic_res.stream_unread_messages + pm_res.total_count,
    };
}

// Saves us from calling to get_counts() when we can avoid it.
export function calculate_notifiable_count(res: FullUnreadCountsData): number {
    let new_message_count = 0;

    const only_show_dm_mention =
        user_settings.desktop_icon_count_display ===
        settings_config.desktop_icon_count_display_values.dm_mention.code;
    const only_show_dm_mention_followed_topic =
        user_settings.desktop_icon_count_display ===
        settings_config.desktop_icon_count_display_values.dm_mention_followed_topic.code;
    const no_notifications =
        user_settings.desktop_icon_count_display ===
        settings_config.desktop_icon_count_display_values.none.code;

    if (only_show_dm_mention || only_show_dm_mention_followed_topic) {
        // DESKTOP_ICON_COUNT_DISPLAY_DM_MENTION
        const dm_mention_count =
            res.mentioned_message_count +
            res.direct_message_count -
            // Avoid double-counting direct messages containing mentions
            res.direct_message_with_mention_count;
        if (only_show_dm_mention_followed_topic) {
            // DESKTOP_ICON_COUNT_DISPLAY_DM_MENTION_FOLLOWED_TOPIC
            // Avoid double-counting followed topic messages containing mentions
            new_message_count =
                dm_mention_count +
                res.followed_topic_unread_messages_count -
                res.followed_topic_unread_messages_with_mention_count;
        } else {
            new_message_count = dm_mention_count;
        }
    } else if (no_notifications) {
        // DESKTOP_ICON_COUNT_DISPLAY_NONE
        new_message_count = 0;
    } else {
        // DESKTOP_ICON_COUNT_DISPLAY_MESSAGES
        new_message_count = res.home_unread_messages;
    }
    return new_message_count;
}

export function get_notifiable_count(): number {
    const res = get_counts();
    return calculate_notifiable_count(res);
}

export function unread_count_info_for_stream(stream_id: number): StreamCountInfo {
    return unread_topic_counter.get_stream_count_info(stream_id);
}

export function num_unread_for_topic(stream_id: number, topic_name: string): number {
    return unread_topic_counter.get(stream_id, topic_name);
}

export function stream_has_any_unread_mentions(stream_id: number): boolean {
    // This function is somewhat inefficient and thus should not be
    // called in loops, since runs in O(total unread mentions) time.
    const streams_with_mentions = unread_topic_counter.get_streams_with_unread_mentions();
    return streams_with_mentions.has(stream_id);
}

export function stream_has_any_unmuted_mentions(stream_id: number): boolean {
    // This function is somewhat inefficient and thus should not be
    // called in loops, since runs in O(total unread mentions) time.
    const streams_with_mentions = unread_topic_counter.get_streams_with_unmuted_mentions();
    return streams_with_mentions.has(stream_id);
}

export function topic_has_any_unread_mentions(stream_id: number, topic: string): boolean {
    // Because this function is called in a loop for every displayed
    // Recent Conversations row, it's important for it to run in O(1) time.
    const topic_key = stream_id + ":" + topic.toLowerCase();
    return (unread_mention_topics.get(topic_key)?.size ?? 0) > 0;
}

export function topic_has_any_unread(stream_id: number, topic: string): boolean {
    return unread_topic_counter.topic_has_any_unread(stream_id, topic);
}

export function get_topics_with_unread_mentions(stream_id: number): Set<string> {
    return unread_topic_counter.get_topics_with_unread_mentions(stream_id);
}

export function num_unread_for_user_ids_string(user_ids_string: string): number {
    return unread_direct_message_counter.num_unread(user_ids_string);
}

export function get_msg_ids_for_stream(stream_id: number): number[] {
    return unread_topic_counter.get_msg_ids_for_stream(stream_id);
}

export function get_msg_ids_for_topic(stream_id: number, topic_name: string): number[] {
    return unread_topic_counter.get_msg_ids_for_topic(stream_id, topic_name);
}

export function get_msg_ids_for_user_ids_string(user_ids_string: string): number[] {
    return unread_direct_message_counter.get_msg_ids_for_user_ids_string(user_ids_string);
}

export function get_msg_ids_for_private(): number[] {
    return unread_direct_message_counter.get_msg_ids();
}

export function get_msg_ids_for_mentions(): number[] {
    const ids = [...unread_mentions_counter];

    return util.sorted_ids(ids);
}

export function get_all_msg_ids(): number[] {
    const ids = [...unread_messages];

    return util.sorted_ids(ids);
}

export function get_missing_topics(opts: {
    stream_id: number;
    topic_dict: FoldDict<TopicHistoryEntry>;
}): {pretty_name: string; message_id: number}[] {
    return unread_topic_counter.get_missing_topics(opts);
}

export function get_msg_ids_for_starred(): number[] {
    // This is here for API consistency sake--we never
    // have unread starred messages.  (Some day we may ironically
    // want to make starring the same as mark-as-unread, but
    // for now starring === reading.)
    return [];
}

type UnreadStreamInfo = {
    stream_id: number;
    topic: string;
    unread_message_ids: number[];
};

type UnreadDirectMessageInfo = {
    other_user_id: number;
    // Deprecated and misleading synonym for other_user_id
    sender_id: number;
    unread_message_ids: number[];
};

type UnreadHuddleInfo = {
    user_ids_string: string;
    unread_message_ids: number[];
};

type UnreadMessagesParams = {
    unread_msgs: {
        pms: UnreadDirectMessageInfo[];
        streams: UnreadStreamInfo[];
        huddles: UnreadHuddleInfo[];
        mentions: number[];
        count: number;
        old_unreads_missing: boolean;
    };
};

export function initialize(params: UnreadMessagesParams): void {
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
