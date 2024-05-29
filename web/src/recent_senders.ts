import _ from "lodash";

import {FoldDict} from "./fold_dict";
import * as message_store from "./message_store";
import type {Message} from "./message_store";
import * as people from "./people";
import type {User} from "./people";

// This class is only exported for unit testing purposes.
// If we find reuse opportunities, we should just put it into
// its own module.
export class IdTracker {
    ids = new Set<number>();

    // We cache the max message id to make sure that
    // typeahead code is efficient.  We don't eagerly
    // compute it, since it's plausible a spammy bot
    // could cause us to process many messages at a time
    // during fetching.
    _cached_max_id: number | undefined = undefined;

    add(id: number): void {
        this.ids.add(id);
        if (this._cached_max_id !== undefined && id > this._cached_max_id) {
            this._cached_max_id = id;
        }
    }

    remove(id: number): void {
        this.ids.delete(id);
        this._cached_max_id = undefined;
    }

    max_id(): number {
        if (this._cached_max_id === undefined) {
            this._cached_max_id = _.max([...this.ids]);
        }
        return this._cached_max_id ?? -1;
    }

    empty(): boolean {
        return this.ids.size === 0;
    }
}

// topic_senders[stream_id][sender_id] = IdTracker
const stream_senders = new Map<number, Map<number, IdTracker>>();

// topic_senders[stream_id][topic_id][sender_id] = IdTracker
const topic_senders = new Map<number, FoldDict<Map<number, IdTracker>>>();

// pm_senders[user_ids_string][user_id] = IdTracker
const pm_senders = new Map<string, Map<number, IdTracker>>();

export function clear_for_testing(): void {
    stream_senders.clear();
    topic_senders.clear();
}

function max_id_for_stream_topic_sender(opts: {
    stream_id: number;
    topic: string;
    sender_id: number;
}): number {
    const {stream_id, topic, sender_id} = opts;
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

function max_id_for_stream_sender(opts: {stream_id: number; sender_id: number}): number {
    const {stream_id, sender_id} = opts;
    const sender_dict = stream_senders.get(stream_id);
    if (!sender_dict) {
        return -1;
    }
    const id_tracker = sender_dict.get(sender_id);
    return id_tracker ? id_tracker.max_id() : -1;
}

function add_stream_message(opts: {
    stream_id: number;
    sender_id: number;
    message_id: number;
}): void {
    const {stream_id, sender_id, message_id} = opts;
    const sender_dict = stream_senders.get(stream_id) ?? new Map<number, IdTracker>();
    const id_tracker = sender_dict.get(sender_id) ?? new IdTracker();
    stream_senders.set(stream_id, sender_dict);
    sender_dict.set(sender_id, id_tracker);
    id_tracker.add(message_id);
}

function add_topic_message(opts: {
    stream_id: number;
    topic: string;
    sender_id: number;
    message_id: number;
}): void {
    const {stream_id, topic, sender_id, message_id} = opts;
    const topic_dict = topic_senders.get(stream_id) ?? new FoldDict();
    const sender_dict = topic_dict.get(topic) ?? new Map<number, IdTracker>();
    const id_tracker = sender_dict.get(sender_id) ?? new IdTracker();
    topic_senders.set(stream_id, topic_dict);
    topic_dict.set(topic, sender_dict);
    sender_dict.set(sender_id, id_tracker);
    id_tracker.add(message_id);
}

export function process_stream_message(message: Message & {type: "stream"}): void {
    const stream_id = message.stream_id;
    const topic = message.topic;
    const sender_id = message.sender_id;
    const message_id = message.id;

    add_stream_message({stream_id, sender_id, message_id});
    add_topic_message({stream_id, topic, sender_id, message_id});
}

function remove_topic_message(opts: {
    stream_id: number;
    topic: string;
    sender_id: number;
    message_id: number;
}): void {
    const {stream_id, topic, sender_id, message_id} = opts;
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

export function process_topic_edit(opts: {
    message_ids: number[];
    old_stream_id: number;
    old_topic: string;
    new_stream_id: number;
    new_topic: string;
}): void {
    const {message_ids, old_stream_id, old_topic, new_stream_id, new_topic} = opts;
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

export function update_topics_of_deleted_message_ids(message_ids: number[]): void {
    for (const message_id of message_ids) {
        const message = message_store.get(message_id);
        if (!message || message.type !== "stream") {
            continue;
        }

        const stream_id = message.stream_id;
        const topic = message.topic;
        const sender_id = message.sender_id;

        remove_topic_message({stream_id, topic, sender_id, message_id});
    }
}

export function compare_by_recency(
    user_a: User,
    user_b: User,
    stream_id: number,
    topic: string,
): number {
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

export function get_topic_recent_senders(stream_id: number, topic: string): number[] {
    const topic_dict = topic_senders.get(stream_id);
    if (topic_dict === undefined) {
        return [];
    }

    const sender_dict = topic_dict.get(topic);
    if (sender_dict === undefined) {
        return [];
    }

    function by_max_message_id(item1: [number, IdTracker], item2: [number, IdTracker]): number {
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

export function process_private_message(opts: {
    to_user_ids: string;
    sender_id: number;
    id: number;
}): void {
    const {to_user_ids, sender_id, id} = opts;
    const sender_dict = pm_senders.get(to_user_ids) ?? new Map<number, IdTracker>();
    const id_tracker = sender_dict.get(sender_id) ?? new IdTracker();
    pm_senders.set(to_user_ids, sender_dict);
    sender_dict.set(sender_id, id_tracker);
    id_tracker.add(id);
}

type DirectMessageSendersInfo = {participants: number[]; non_participants: number[]};
export function get_pm_recent_senders(user_ids_string: string): DirectMessageSendersInfo {
    const user_ids = [...people.get_participants_from_user_ids_string(user_ids_string)];
    const sender_dict = pm_senders.get(user_ids_string);
    const pm_senders_info: DirectMessageSendersInfo = {participants: [], non_participants: []};
    if (sender_dict === undefined) {
        return pm_senders_info;
    }

    for (const user_id of user_ids) {
        if (sender_dict.get(user_id)) {
            pm_senders_info.participants.push(user_id);
        } else {
            pm_senders_info.non_participants.push(user_id);
        }
    }
    pm_senders_info.participants.sort((user_id1: number, user_id2: number) => {
        const max_id1 = sender_dict.get(user_id1)?.max_id() ?? -1;
        const max_id2 = sender_dict.get(user_id2)?.max_id() ?? -1;
        return max_id2 - max_id1;
    });
    return pm_senders_info;
}

export function get_topic_message_ids_for_sender(
    stream_id: number,
    topic: string,
    sender_id: number,
): Set<number> {
    const id_tracker = topic_senders?.get(stream_id)?.get(topic)?.get(sender_id);
    if (id_tracker === undefined) {
        return new Set();
    }
    return id_tracker.ids;
}
