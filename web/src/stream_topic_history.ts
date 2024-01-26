import assert from "minimalistic-assert";
import {z} from "zod";

import {all_messages_data} from "./all_messages_data";
import * as channel from "./channel";
import {FoldDict} from "./fold_dict";
import * as message_util from "./message_util";
import * as stream_topic_history_util from "./stream_topic_history_util";
import * as sub_store from "./sub_store";
import type {StreamSubscription} from "./sub_store";
import * as topic_list from "./topic_list";
import * as unread from "./unread";

// stream_id -> PerStreamHistory object
const stream_dict = new Map<number, PerStreamHistory>();
const fetched_stream_ids = new Set<number>();
const request_pending_stream_ids = new Set<number>();

export function all_topics_in_cache(sub: StreamSubscription): boolean {
    // Checks whether this browser's cache of contiguous messages
    // (used to locally render narrows) in all_messages_data has all
    // messages from a given stream, and thus all historical topics
    // for it.  Because all_messages_data is a range, we just need to
    // compare it to the range of history on the stream.

    // If the cache isn't initialized, it's a clear false.
    if (all_messages_data === undefined || all_messages_data.empty()) {
        return false;
    }

    // If the cache doesn't have the latest messages, we can't be sure
    // we have all topics.
    if (!all_messages_data.fetch_status.has_found_newest()) {
        return false;
    }

    if (sub.first_message_id === null) {
        // If the stream has no message history, we have it all
        // vacuously.  This should be a very rare condition, since
        // stream creation sends a message.
        return true;
    }

    // Now, we can just compare the first cached message to the first
    // message ID in the stream; if it's older, we're good, otherwise,
    // we might be missing the oldest topics in this stream in our
    // cache.
    const first_cached_message = all_messages_data.first();
    return first_cached_message.id <= sub.first_message_id;
}

export function is_complete_for_stream_id(stream_id: number): boolean {
    if (fetched_stream_ids.has(stream_id)) {
        return true;
    }

    const sub = sub_store.get(stream_id);
    const in_cache = sub !== undefined && all_topics_in_cache(sub);

    if (in_cache) {
        /*
            If the stream is cached, we can add it to
            fetched_stream_ids.  Note that for the opposite
            scenario, we don't delete from
            fetched_stream_ids, because we may just be
            waiting for the initial message fetch.
        */
        fetched_stream_ids.add(stream_id);
    }

    return in_cache;
}

export function stream_has_topics(stream_id: number): boolean {
    if (!stream_dict.has(stream_id)) {
        return false;
    }

    const history = stream_dict.get(stream_id);
    assert(history !== undefined);

    return history.has_topics();
}

export type TopicHistoryEntry = {
    is_data_reliable: boolean;
    message_id: number;
    pretty_name: string;
};

type ServerTopicHistoryEntry = {
    name: string;
    max_id: number;
};

export class PerStreamHistory {
    /*
        For a given stream, this structure has a dictionary of topics.
        The main getter of this object is get_recent_topic_names, and
        we just sort on the fly every time we are called.

        Attributes for a topic are:
        * message_id: The latest message_id in the topic.  Only usable
          for imprecise applications like sorting.  The message_id
          cannot be fully accurate given message editing and deleting
          (as we don't have a way to handle the latest message in a
          stream having its stream edited or deleted).

          TODO: We can probably fix this limitation by doing a
          single-message `GET /messages` query with anchor="latest",
          num_before=0, num_after=0, to update this field when its
          value becomes ambiguous.  Or probably better to avoid a
          thundering herd (of a fast query), having the server send
          the data needed to do this update in stream/topic-edit and
          delete events (just the new max_message_id for the relevant
          topic would likely suffice, though we need to think about
          private stream corner cases).
        * pretty_name: The topic_name, with original case.
        * is_data_reliable: Whether the message_id field is absolutely
          correct and is set to the latest message_id.
    */

    topics = new FoldDict<TopicHistoryEntry>();
    // Most recent message ID for the stream.
    max_message_id = 0;
    stream_id: number;

    constructor(stream_id: number) {
        this.stream_id = stream_id;
    }

    has_topics(): boolean {
        return this.topics.size !== 0;
    }

    update_stream_max_message_id(message_id: number): void {
        if (message_id > this.max_message_id) {
            this.max_message_id = message_id;
        }
    }

    add_or_update(topic_name: string, message_id: number, is_data_reliable: boolean): void {
        this.update_stream_max_message_id(message_id);

        const existing = this.topics.get(topic_name);

        if (!existing) {
            this.topics.set(topic_name, {
                message_id,
                pretty_name: topic_name,
                is_data_reliable,
            });
            return;
        }

        if (!existing.is_data_reliable && is_data_reliable) {
            existing.is_data_reliable = true;
        }

        if (message_id > existing.message_id) {
            existing.message_id = message_id;
            existing.pretty_name = topic_name;
        }
    }

    add_history(server_history: ServerTopicHistoryEntry[]): void {
        // This method populates historical topics from the
        // server.  We have less data about these than the
        // client can maintain for newer topics.

        for (const obj of server_history) {
            const topic_name = obj.name;
            const message_id = obj.max_id;

            const existing = this.topics.get(topic_name);

            if (existing && existing.is_data_reliable) {
                // Trust out local data more.
                continue;
            }

            // If we get here, we are either finding out about
            // the topic for the first time, or we are getting
            // more current data for it.

            this.topics.set(topic_name, {
                message_id,
                pretty_name: topic_name,
                is_data_reliable: true,
            });
            this.update_stream_max_message_id(message_id);
        }
    }

    get_recent_topic_names(): string[] {
        const my_recents = [...this.topics.values()];

        /* Add any older topics with unreads that may not be present
         * in our local cache. */
        const missing_topics = unread.get_missing_topics({
            stream_id: this.stream_id,
            topic_dict: this.topics,
        });

        const recents = [...my_recents, ...missing_topics];

        recents.sort((a, b) => b.message_id - a.message_id);

        const names = recents.map((obj) => obj.pretty_name);

        return names;
    }

    get_max_message_id(): number {
        return this.max_message_id;
    }
}

const message_response_schema = z.object({
    messages: z.array(
        z.object({
            id: z.number(),
        }),
    ),
});

function get_latest_message_in_topic(
    stream_id: number,
    topic_name: string,
    success_cb: (max_message_id: number | undefined) => void,
): void {
    const data = {
        anchor: "newest",
        num_before: 1,
        num_after: 0,
        narrow: JSON.stringify([
            {operator: "stream", operand: stream_id},
            {operator: "topic", operand: topic_name},
        ]),
    };

    void channel.get({
        url: "/json/messages",
        data,
        success(response_data) {
            const data = message_response_schema.parse(response_data);
            let latest_message_id;
            if (data.messages.length !== 0) {
                latest_message_id = data.messages[0].id;
            }
            success_cb(latest_message_id);
        },
    });
}

export function remove_messages(opts: {
    stream_id: number;
    topic_name: string;
    max_removed_msg_id: number;
    topic_deleted: boolean;
}): void {
    const stream_id = opts.stream_id;
    const topic_name = opts.topic_name;
    const max_removed_msg_id = opts.max_removed_msg_id;
    const history = stream_dict.get(stream_id);

    // This is the special case of "removing" a message from
    // a topic, which happens when we edit topics.

    if (!history) {
        return;
    }

    const existing_topic = history.topics.get(topic_name);
    if (!existing_topic) {
        return;
    }

    if (opts.topic_deleted) {
        // topic_deleted is true only when propagate_mode is
        // set to change_all and here we can be sure that the
        // topic will no longer exist, so we will remove the
        // topic completely.
        history.topics.delete(topic_name);
        return;
    }

    // Update max_message_id in topic
    if (existing_topic.message_id <= max_removed_msg_id) {
        const msgs_in_topic = message_util.get_messages_in_topic(stream_id, topic_name);

        if (!msgs_in_topic.length) {
            get_latest_message_in_topic(stream_id, topic_name, (latest_message_id) => {
                if (!latest_message_id) {
                    history.topics.delete(topic_name);
                } else {
                    existing_topic.message_id = latest_message_id;
                    existing_topic.is_data_reliable = true;
                }
                // We already call stream_list.update_streams_sidebar()
                // towards the end of message_events.update_messages
                // to rebuild the topic list, but we might not have
                // got the correct data from the server by the time
                // update_streams_sidebar gets called. So, this call
                // to rebuild the topic list ensures that the order
                // of topics is updated as per the latest data.
                if (topic_list.active_stream_id() === stream_id) {
                    const $stream_li = topic_list.get_stream_li();
                    assert($stream_li !== undefined);
                    topic_list.rebuild($stream_li, stream_id);
                }
            });
            return;
        }

        let max_message_id = 0;
        for (const msg of msgs_in_topic) {
            if (msg.id > max_message_id) {
                max_message_id = msg.id;
            }
        }
        existing_topic.message_id = max_message_id;
    }

    // Update max_message_id in stream
    if (history.max_message_id <= max_removed_msg_id) {
        history.max_message_id = message_util.get_max_message_id_in_stream(stream_id);
    }
}

export function find_or_create(stream_id: number): PerStreamHistory {
    let history = stream_dict.get(stream_id);

    if (!history) {
        history = new PerStreamHistory(stream_id);
        stream_dict.set(stream_id, history);
    }

    return history;
}

export function add_message(opts: {
    stream_id: number;
    message_id: number;
    topic_name: string;
    is_data_reliable: boolean;
}): void {
    const stream_id = opts.stream_id;
    const message_id = opts.message_id;
    const topic_name = opts.topic_name;
    const is_data_reliable = opts.is_data_reliable;

    const history = find_or_create(stream_id);

    history.add_or_update(topic_name, message_id, is_data_reliable);
}

export function add_moved_message(opts: {
    stream_id: number;
    max_moved_message_id: number;
    topic_name: string;
    can_latest_message_be_inaccessible: boolean;
}): void {
    const stream_id = opts.stream_id;
    const history = find_or_create(stream_id);

    const topic_name = opts.topic_name;
    const existing_topic = history.topics.get(topic_name);
    const max_moved_message_id = opts.max_moved_message_id;

    if (existing_topic && existing_topic.message_id > max_moved_message_id) {
        // In this case, the topic order will not change irrespective
        // of whether there can be a case where message_id is inaccessible
        // or the data we already have is reliable or not. So we just
        // skip.
        return;
    }

    if (!opts.can_latest_message_be_inaccessible) {
        // We are certain that the value of message_id field
        // is reliable, i.e. we can access the message.
        // We would update the data in two cases -
        // 1. Topic with same name exists already.
        // 2. We are sure that there is no existing topic with
        // same name in this stream.
        if (existing_topic !== undefined || is_complete_for_stream_id(stream_id)) {
            const is_data_reliable = existing_topic ? existing_topic.is_data_reliable : true;
            history.add_or_update(topic_name, max_moved_message_id, is_data_reliable);
            return;
        }

        // The data we have from moved message event is reliable but
        // we do not know whether there already exists a topic with
        // same name in the stream. So, here we need to go to the
        // server to get the correct data. But we only go to the
        // server if we show the topic list in sidebar or else
        // we just skip it.
        if (topic_list.active_stream_id() !== stream_id) {
            // The stream is not opened in sidebar and we do not need
            // to update topic list.
            return;
        }

        // We would fetch the complete topic history of the stream because
        // we do not want to show the current topic in incorrect order as
        // we have not fetched all the topics data till now.
        stream_topic_history_util.get_server_history(stream_id, () => {
            // We already call stream_list.update_streams_sidebar()
            // towards the end of message_events.update_messages
            // to rebuild the topic list, but we might not have
            // got the correct data from the server by the time
            // update_streams_sidebar gets called. So, this call
            // to rebuild the topic list ensures that the order
            // of topics is updated as per the latest data.
            const $stream_li = topic_list.get_stream_li();
            assert($stream_li !== undefined);
            topic_list.rebuild($stream_li, stream_id);
        });
        return;
    }

    // If the code reaches this point there are two cases -
    // 1. None of the moved messages are available locally with the client.
    // 2. The latest message among the moved messages is not available locally.

    if (topic_list.active_stream_id() !== stream_id) {
        // The stream is not opened in sidebar and we do not need
        // to update topic list.
        // But we would need to handle cases where the data would
        // not be updated correctly in future -
        // 1. We have no data for this topic and the client has already fetched
        // full history for the stream.
        // 2. The topic already exists for the stream and is_data_reliable is
        // set to true.
        if (!existing_topic && fetched_stream_ids.has(stream_id)) {
            fetched_stream_ids.delete(stream_id);
        } else if (existing_topic && existing_topic.is_data_reliable) {
            existing_topic.is_data_reliable = false;
        }
        return;
    }

    const $stream_li = topic_list.get_stream_li();
    assert($stream_li !== undefined);

    if (existing_topic) {
        // Since there already exists a topic with same name, we just need to
        // get the data for this topic from the server.
        // Even if the client does not have complete topic data for the stream
        // the order of the topics will not be affected since the topic will
        // only move towards top if needed.
        get_latest_message_in_topic(stream_id, topic_name, (latest_message_id) => {
            assert(latest_message_id !== undefined);
            history.add_or_update(topic_name, latest_message_id, true);

            // We already call stream_list.update_streams_sidebar()
            // towards the end of message_events.update_messages
            // to rebuild the topic list, but we might not have
            // got the correct data from the server by the time
            // update_streams_sidebar gets called. So, this call
            // to rebuild the topic list ensures that the order
            // of topics is updated as per the latest data.
            topic_list.rebuild($stream_li, stream_id);
        });
        return;
    }

    // If there is no existing topic with same name, we fetch the complete
    // history in case we know that we do not have all topics of the stream
    // yet to make sure we do not show incorrect order of topics. If we have
    // other topics of the stream, we just fetch the data for current topic
    // to make sure we do not set the message_id field to some inaccessible
    // message ID.
    if (is_complete_for_stream_id(stream_id)) {
        get_latest_message_in_topic(stream_id, topic_name, (latest_message_id) => {
            assert(latest_message_id !== undefined);
            history.add_or_update(topic_name, latest_message_id, true);
            topic_list.rebuild($stream_li, stream_id);
        });
    } else {
        stream_topic_history_util.get_server_history(stream_id, () => {
            topic_list.rebuild($stream_li, stream_id);
        });
    }
}

export function add_history(stream_id: number, server_history: ServerTopicHistoryEntry[]): void {
    const history = find_or_create(stream_id);
    history.add_history(server_history);
    fetched_stream_ids.add(stream_id);
}

export function has_history_for(stream_id: number): boolean {
    return fetched_stream_ids.has(stream_id);
}

export function get_recent_topic_names(stream_id: number): string[] {
    const history = find_or_create(stream_id);

    return history.get_recent_topic_names();
}

export function get_max_message_id(stream_id: number): number {
    const history = find_or_create(stream_id);

    return history.get_max_message_id();
}

export function reset(): void {
    // This is only used by tests.
    stream_dict.clear();
    fetched_stream_ids.clear();
    request_pending_stream_ids.clear();
}

export function is_request_pending_for(stream_id: number): boolean {
    return request_pending_stream_ids.has(stream_id);
}

export function add_request_pending_for(stream_id: number): void {
    request_pending_stream_ids.add(stream_id);
}

export function remove_request_pending_for(stream_id: number): void {
    request_pending_stream_ids.delete(stream_id);
}
