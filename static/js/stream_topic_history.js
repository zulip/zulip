"use strict";

const {FoldDict} = require("./fold_dict");

const stream_dict = new Map(); // stream_id -> PerStreamHistory object
const fetched_stream_ids = new Set();

exports.is_complete_for_stream_id = (stream_id) => {
    if (fetched_stream_ids.has(stream_id)) {
        return true;
    }

    /*
        TODO: We should possibly move all_topics_in_cache
        from stream_data to here, since the function
        mostly looks at message_list.all and has little
        to do with typical stream_data stuff.  (We just
        need sub.first_message_id.)
    */
    const sub = stream_data.get_sub_by_id(stream_id);
    const in_cache = stream_data.all_topics_in_cache(sub);

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
};

exports.stream_has_topics = function (stream_id) {
    if (!stream_dict.has(stream_id)) {
        return false;
    }

    const history = stream_dict.get(stream_id);

    return history.has_topics();
};

class PerStreamHistory {
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

    add_or_update(opts) {
        const topic_name = opts.topic_name;
        let message_id = opts.message_id || 0;

        message_id = Number.parseInt(message_id, 10);
        this.update_stream_max_message_id(message_id);

        const existing = this.topics.get(topic_name);

        if (!existing) {
            this.topics.set(opts.topic_name, {
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
        const my_recents = Array.from(this.topics.values());

        const missing_topics = unread.get_missing_topics({
            stream_id: this.stream_id,
            topic_dict: this.topics,
        });

        const recents = my_recents.concat(missing_topics);

        recents.sort((a, b) => b.message_id - a.message_id);

        const names = recents.map((obj) => obj.pretty_name);

        return names;
    }

    get_max_message_id() {
        return this.max_message_id;
    }
}
exports.PerStreamHistory = PerStreamHistory;

exports.remove_messages = function (opts) {
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
};

exports.find_or_create = function (stream_id) {
    let history = stream_dict.get(stream_id);

    if (!history) {
        history = new PerStreamHistory(stream_id);
        stream_dict.set(stream_id, history);
    }

    return history;
};

exports.add_message = function (opts) {
    const stream_id = opts.stream_id;
    const message_id = opts.message_id;
    const topic_name = opts.topic_name;

    const history = exports.find_or_create(stream_id);

    history.add_or_update({
        topic_name,
        message_id,
    });
};

exports.add_history = function (stream_id, server_history) {
    const history = exports.find_or_create(stream_id);
    history.add_history(server_history);
    fetched_stream_ids.add(stream_id);
};

exports.get_server_history = function (stream_id, on_success) {
    if (fetched_stream_ids.has(stream_id)) {
        on_success();
        return;
    }

    const url = "/json/users/me/" + stream_id + "/topics";

    channel.get({
        url,
        data: {},
        success(data) {
            const server_history = data.topics;
            exports.add_history(stream_id, server_history);
            on_success();
        },
    });
};

exports.get_recent_topic_names = function (stream_id) {
    const history = exports.find_or_create(stream_id);

    return history.get_recent_topic_names();
};

exports.get_max_message_id = function (stream_id) {
    const history = exports.find_or_create(stream_id);

    return history.get_max_message_id();
};

exports.reset = function () {
    // This is only used by tests.
    stream_dict.clear();
    fetched_stream_ids.clear();
};

window.stream_topic_history = exports;
