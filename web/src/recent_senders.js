import _ from "lodash";

import {FoldDict} from "./fold_dict";
import * as message_store from "./message_store";
import * as people from "./people";

// This class is only exported for unit testing purposes.
// If we find reuse opportunities, we should just put it into
// its own module.
export class IdTracker {
    ids = new Set();

    // We cache the max message id to make sure that
    // typeahead code is efficient.  We don't eagerly
    // compute it, since it's plausible a spammy bot
    // could cause us to process many messages at a time
    // during fetching.
    _cached_max_id = undefined;

    add(id) {
        this.ids.add(id);
        if (this._cached_max_id !== undefined && id > this._cached_max_id) {
            this._cached_max_id = id;
        }
    }

    remove(id) {
        this.ids.delete(id);
        this._cached_max_id = undefined;
    }

    max_id() {
        if (this._cached_max_id === undefined) {
            this._cached_max_id = _.max([...this.ids]);
        }
        return this._cached_max_id || -1;
    }

    empty() {
        return this.ids.size === 0;
    }
}

// topic_senders[stream_id][sender_id] = IdTracker
const stream_senders = new Map();

// topic_senders[stream_id][topic_id][sender_id] = IdTracker
const topic_senders = new Map();

// pm_senders[user_ids_string][user_id] = IdTracker
const pm_senders = new Map();

export function clear_for_testing() {
    stream_senders.clear();
    topic_senders.clear();
}

function max_id_for_stream_topic_sender({stream_id, topic, sender_id}) {
    const topic_dict = topic_senders.get(stream_id);
    if (!topic_dict) {
        return -1;
    }
    const sender_dict = topic_dict.get(topic);
    if (!sender_dict) {
        return -1;
    }
    const id_tracker = sender_dict.get(sender_id);
    return id_tracker ? id_tracker.max_id() : -1;
}

function max_id_for_stream_sender({stream_id, sender_id}) {
    const sender_dict = stream_senders.get(stream_id);
    if (!sender_dict) {
        return -1;
    }
    const id_tracker = sender_dict.get(sender_id);
    return id_tracker ? id_tracker.max_id() : -1;
}

function add_stream_message({stream_id, sender_id, message_id}) {
    const sender_dict = stream_senders.get(stream_id) || new Map();
    const id_tracker = sender_dict.get(sender_id) || new IdTracker();
    stream_senders.set(stream_id, sender_dict);
    sender_dict.set(sender_id, id_tracker);
    id_tracker.add(message_id);
}

function add_topic_message({stream_id, topic, sender_id, message_id}) {
    const topic_dict = topic_senders.get(stream_id) || new FoldDict();
    const sender_dict = topic_dict.get(topic) || new Map();
    const id_tracker = sender_dict.get(sender_id) || new IdTracker();
    topic_senders.set(stream_id, topic_dict);
    topic_dict.set(topic, sender_dict);
    sender_dict.set(sender_id, id_tracker);
    id_tracker.add(message_id);
}

export function process_stream_message(message) {
    const stream_id = message.stream_id;
    const topic = message.topic;
    const sender_id = message.sender_id;
    const message_id = message.id;

    add_stream_message({stream_id, sender_id, message_id});
    add_topic_message({stream_id, topic, sender_id, message_id});
}

function remove_topic_message({stream_id, topic, sender_id, message_id}) {
    const topic_dict = topic_senders.get(stream_id);
    if (!topic_dict) {
        return;
    }

    const sender_dict = topic_dict.get(topic);

    if (!sender_dict) {
        return;
    }

    const id_tracker = sender_dict.get(sender_id);

    if (!id_tracker) {
        return;
    }

    id_tracker.remove(message_id);
    if (id_tracker.empty()) {
        sender_dict.delete(sender_id);
    }

    if (sender_dict.size === 0) {
        topic_dict.delete(topic);
    }
}

export function process_topic_edit({
    message_ids,
    old_stream_id,
    old_topic,
    new_stream_id,
    new_topic,
}) {
    // Note that we don't delete anything from stream_senders here.
    // Our view is that it's probably better to not do so; users who
    // recently posted to a stream are relevant for typeahead even if
    // the messages were moved to another stream or deleted.

    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        if (!message) {
            continue;
        }
        const sender_id = message.sender_id;

        remove_topic_message({stream_id: old_stream_id, topic: old_topic, sender_id, message_id});
        add_topic_message({stream_id: new_stream_id, topic: new_topic, sender_id, message_id});

        add_stream_message({stream_id: new_stream_id, sender_id, message_id});
    }
}

export function update_topics_of_deleted_message_ids(message_ids) {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        if (!message) {
            continue;
        }

        const stream_id = message.stream_id;
        const topic = message.topic;
        const sender_id = message.sender_id;

        remove_topic_message({stream_id, topic, sender_id, message_id});
    }
}

export function compare_by_recency(user_a, user_b, stream_id, topic) {
    let a_message_id;
    let b_message_id;

    a_message_id = max_id_for_stream_topic_sender({stream_id, topic, sender_id: user_a.user_id});
    b_message_id = max_id_for_stream_topic_sender({stream_id, topic, sender_id: user_b.user_id});

    if (a_message_id !== b_message_id) {
        return b_message_id - a_message_id;
    }

    a_message_id = max_id_for_stream_sender({stream_id, sender_id: user_a.user_id});
    b_message_id = max_id_for_stream_sender({stream_id, sender_id: user_b.user_id});

    return b_message_id - a_message_id;
}

export function get_topic_recent_senders(stream_id, topic) {
    const topic_dict = topic_senders.get(stream_id);
    if (topic_dict === undefined) {
        return [];
    }

    const sender_dict = topic_dict.get(topic);
    if (sender_dict === undefined) {
        return [];
    }

    function by_max_message_id(item1, item2) {
        const list1 = item1[1];
        const list2 = item2[1];
        return list2.max_id() - list1.max_id();
    }

    const sorted_senders = [...sender_dict.entries()].sort(by_max_message_id);
    const recent_senders = [];
    for (const item of sorted_senders) {
        recent_senders.push(item[0]);
    }
    return recent_senders;
}

export function process_private_message({to_user_ids, sender_id, id}) {
    const sender_dict = pm_senders.get(to_user_ids) || new Map();
    const id_tracker = sender_dict.get(sender_id) || new IdTracker();
    pm_senders.set(to_user_ids, sender_dict);
    sender_dict.set(sender_id, id_tracker);
    id_tracker.add(id);
}

export function get_pm_recent_senders(user_ids_string) {
    const user_ids = [...people.get_participants_from_user_ids_string(user_ids_string)];
    const sender_dict = pm_senders.get(user_ids_string);
    const pm_senders_info = {participants: [], non_participants: []};
    if (!sender_dict) {
        return pm_senders_info;
    }

    function compare_pm_user_ids_by_recency(user_id1, user_id2) {
        const max_id1 = sender_dict.get(user_id1)?.max_id() || -1;
        const max_id2 = sender_dict.get(user_id2)?.max_id() || -1;
        return max_id2 - max_id1;
    }

    pm_senders_info.non_participants = user_ids.filter((user_id) => {
        if (sender_dict.get(user_id)) {
            pm_senders_info.participants.push(user_id);
            return false;
        }
        return true;
    });
    pm_senders_info.participants.sort(compare_pm_user_ids_by_recency);
    return pm_senders_info;
}
