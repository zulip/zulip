import {all_messages_data} from "./all_messages_data";
import {FoldDict} from "./fold_dict";
import * as message_util from "./message_util";
import * as sub_store from "./sub_store";
import * as unread from "./unread";

const stream_dict = new Map(); // stream_id -> PerStreamHistory object
const fetched_stream_ids = new Set();

export function all_topics_in_cache(sub) {
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

export function is_complete_for_stream_id(stream_id) {
    if (fetched_stream_ids.has(stream_id)) {
        return true;
    }

    const sub = sub_store.get(stream_id);
    const in_cache = all_topics_in_cache(sub);

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

export function stream_has_topics(stream_id) {
    if (!stream_dict.has(stream_id)) {
        return false;
    }

    const history = stream_dict.get(stream_id);

    return history.has_topics();
}

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
        * historical: Whether the user actually received any messages in
          the topic (has UserMessage rows) or is just viewing the stream.
        * count: Number of known messages in the topic.  Used to detect
          when the last messages in a topic were moved to other topics or
          deleted.
    */

    topics = new FoldDict();
    // Most recent message ID for the stream.
    max_message_id = 0;

    constructor(stream_id) {
        this.stream_id = stream_id;
    }

    has_topics() {
        return this.topics.size !== 0;
    }

    update_stream_max_message_id(message_id) {
        if (message_id > this.max_message_id) {
            this.max_message_id = message_id;
        }
    }

    add_or_update({topic_name, message_id = 0}) {
        message_id = Number.parseInt(message_id, 10);
        this.update_stream_max_message_id(message_id);

        const existing = this.topics.get(topic_name);

        if (!existing) {
            this.topics.set(topic_name, {
                message_id,
                pretty_name: topic_name,
                historical: false,
                count: 1,
            });
            return;
        }

        if (!existing.historical) {
            existing.count += 1;
        }

        if (message_id > existing.message_id) {
            existing.message_id = message_id;
            existing.pretty_name = topic_name;
        }
    }

    maybe_remove(topic_name, num_messages) {
        const existing = this.topics.get(topic_name);

        if (!existing) {
            return;
        }

        if (existing.historical) {
            // We can't trust that a topic rename applied to
            // the entire history of historical topic, so we
            // will always leave it in the sidebar.
            return;
        }

        if (existing.count <= num_messages) {
            this.topics.delete(topic_name);
            return;
        }

        existing.count -= num_messages;
    }

    add_history(server_history) {
        // This method populates historical topics from the
        // server.  We have less data about these than the
        // client can maintain for newer topics.

        for (const obj of server_history) {
            const topic_name = obj.name;
            const message_id = obj.max_id;

            const existing = this.topics.get(topic_name);

            if (existing && !existing.historical) {
                // Trust out local data more, since it
                // maintains counts.
                continue;
            }

            // If we get here, we are either finding out about
            // the topic for the first time, or we are getting
            // more current data for it.

            this.topics.set(topic_name, {
                message_id,
                pretty_name: topic_name,
                historical: true,
            });
            this.update_stream_max_message_id(message_id);
        }
    }

    get_recent_topic_names() {
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

    get_max_message_id() {
        return this.max_message_id;
    }
}

export function remove_messages(opts) {
    const stream_id = opts.stream_id;
    const topic_name = opts.topic_name;
    const num_messages = opts.num_messages;
    const max_removed_msg_id = opts.max_removed_msg_id;
    const history = stream_dict.get(stream_id);

    // This is the special case of "removing" a message from
    // a topic, which happens when we edit topics.

    if (!history) {
        return;
    }

    // This is the normal case of an incoming message.
    history.maybe_remove(topic_name, num_messages);

    const existing_topic = history.topics.get(topic_name);
    if (!existing_topic) {
        return;
    }

    // Update max_message_id in topic
    if (existing_topic.message_id <= max_removed_msg_id) {
        const msgs_in_topic = message_util.get_messages_in_topic(stream_id, topic_name);
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

export function find_or_create(stream_id) {
    let history = stream_dict.get(stream_id);

    if (!history) {
        history = new PerStreamHistory(stream_id);
        stream_dict.set(stream_id, history);
    }

    return history;
}

export function add_message(opts) {
    const stream_id = opts.stream_id;
    const message_id = opts.message_id;
    const topic_name = opts.topic_name;

    const history = find_or_create(stream_id);

    history.add_or_update({
        topic_name,
        message_id,
    });
}

export function add_history(stream_id, server_history) {
    const history = find_or_create(stream_id);
    history.add_history(server_history);
    fetched_stream_ids.add(stream_id);
}

export function has_history_for(stream_id) {
    return fetched_stream_ids.has(stream_id);
}

export function get_recent_topic_names(stream_id) {
    const history = find_or_create(stream_id);

    return history.get_recent_topic_names();
}

export function get_max_message_id(stream_id) {
    const history = find_or_create(stream_id);

    return history.get_max_message_id();
}

export function reset() {
    // This is only used by tests.
    stream_dict.clear();
    fetched_stream_ids.clear();
}
