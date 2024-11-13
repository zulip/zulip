import assert from "minimalistic-assert";

import * as blueslip from "./blueslip.ts";
import {Filter} from "./filter.ts";
import * as message_lists from "./message_lists.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {NarrowTerm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as unread from "./unread.ts";

export function filter(): Filter | undefined {
    // `Recent Conversations` and `Inbox` return undefined;
    return message_lists.current?.data.filter;
}

export function search_terms(current_filter: Filter | undefined = filter()): NarrowTerm[] {
    if (current_filter === undefined) {
        if (page_params.narrow !== undefined) {
            return new Filter(page_params.narrow).terms();
        }
        return new Filter([]).terms();
    }
    return current_filter.terms();
}

export function is_search_view(current_filter: Filter | undefined = filter()): boolean {
    if (current_filter && !current_filter.supports_collapsing_recipients()) {
        return true;
    }
    return false;
}

export function is_message_feed_visible(): boolean {
    // It's important that `message_lists.current` is the
    // source of truth for this since during the initial app load,
    // `message_lists.current` is `undefined` and we don't want
    // to return `true` if we haven't loaded the message feed yet.
    return message_lists.current !== undefined;
}

export function update_email(
    user_id: number,
    new_email: string,
    current_filter: Filter | undefined = filter(),
): void {
    if (current_filter !== undefined) {
        current_filter.update_email(user_id, new_email);
    }
}

/* Search terms we should send to the server. */
export function public_search_terms(
    current_filter: Filter | undefined = filter(),
): NarrowTerm[] | undefined {
    if (current_filter === undefined) {
        return undefined;
    }
    return current_filter.public_terms();
}

// Collect terms which appear only once into a map,
// and discard those which appear more than once.
function collect_single(terms: NarrowTerm[]): Map<string, string> {
    const seen = new Set<string>();
    const result = new Map<string, string>();

    for (const term of terms) {
        const key = term.operator;
        if (seen.has(key)) {
            result.delete(key);
        } else {
            result.set(key, term.operand);
            seen.add(key);
        }
    }

    return result;
}

// Modify default compose parameters (stream etc.) based on
// the current narrowed view.
//
// This logic is here and not in the 'compose' module because
// it will get more complicated as we add things to the narrow
// search term language.
export function set_compose_defaults(): {
    stream_id?: number;
    topic?: string;
    private_message_recipient?: string;
} {
    const opts: {stream_id?: number; topic?: string; private_message_recipient?: string} = {};
    const single = collect_single(search_terms());

    // Set the stream, topic, and/or direct message recipient
    // if they are uniquely specified in the narrow view.

    if (single.has("channel")) {
        // The raw stream name from collect_single may be an arbitrary
        // unvalidated string from the URL fragment and thus not be valid.
        // So we look up the resolved stream and return that if appropriate.
        const sub = stream_sub();
        if (sub !== undefined) {
            opts.stream_id = sub.stream_id;
        }
    }

    const topic = single.get("topic");
    if (topic !== undefined) {
        opts.topic = topic;
    }

    const private_message_recipient = single.get("dm");
    if (
        private_message_recipient !== undefined &&
        people.is_valid_bulk_emails_for_compose(private_message_recipient.split(","))
    ) {
        opts.private_message_recipient = private_message_recipient;
    }
    return opts;
}

export let stream_id = (current_filter: Filter | undefined = filter()): number | undefined => {
    if (current_filter === undefined) {
        return undefined;
    }
    const stream_operands = current_filter.operands("channel");
    if (stream_operands.length === 1 && stream_operands[0] !== undefined) {
        return Number.parseInt(stream_operands[0], 10);
    }
    return undefined;
};

export function rewire_stream_id(value: typeof stream_id): void {
    stream_id = value;
}

export function stream_name(current_filter: Filter | undefined = filter()): string | undefined {
    const id = stream_id(current_filter);
    if (id === undefined) {
        return undefined;
    }
    const sub = stream_data.get_sub_by_id(id);
    return sub?.name;
}

export function stream_sub(
    current_filter: Filter | undefined = filter(),
): StreamSubscription | undefined {
    if (current_filter === undefined) {
        return undefined;
    }
    const stream_operands = current_filter.operands("channel");

    if (stream_operands.length !== 1 || stream_operands[0] === undefined) {
        return undefined;
    }
    return stream_data.get_sub_by_id_string(stream_operands[0]);
}

export let topic = (current_filter: Filter | undefined = filter()): string | undefined => {
    if (current_filter === undefined) {
        return undefined;
    }
    const operands = current_filter.operands("topic");
    if (operands.length === 1) {
        return operands[0];
    }
    return undefined;
};

export function rewire_topic(value: typeof topic): void {
    topic = value;
}

export function pm_ids_string(filter?: Filter): string | undefined {
    // If you are narrowed to a group direct message with
    // users 4, 5, and 99, this will return "4,5,99"
    const emails_string = pm_emails_string(filter);

    if (!emails_string) {
        return undefined;
    }

    const user_ids_string = people.reply_to_to_user_ids_string(emails_string);

    return user_ids_string;
}

export let pm_ids_set = (filter?: Filter): Set<number> => {
    const ids_string = pm_ids_string(filter);
    const pm_ids_list = ids_string ? people.user_ids_string_to_ids_array(ids_string) : [];
    return new Set(pm_ids_list);
};

export function rewire_pm_ids_set(value: typeof pm_ids_set): void {
    pm_ids_set = value;
}

export function pm_emails_string(
    current_filter: Filter | undefined = filter(),
): string | undefined {
    if (current_filter === undefined) {
        return undefined;
    }

    const operands = current_filter.operands("dm");
    if (operands.length !== 1) {
        return undefined;
    }

    return operands[0];
}

export let get_first_unread_info = (
    current_filter: Filter | undefined = filter(),
): {flavor: "cannot_compute" | "not_found"} | {flavor: "found"; msg_id: number} => {
    const cannot_compute_response: {flavor: "cannot_compute"} = {flavor: "cannot_compute"};
    if (current_filter === undefined) {
        // we don't yet support the all-messages view
        blueslip.error("unexpected call to get_first_unread_info");
        return cannot_compute_response;
    }

    if (!current_filter.can_apply_locally()) {
        // For things like search queries, where the server has info
        // that the client isn't privy to, we need to wait for the
        // server to give us a definitive list of messages before
        // deciding where we'll move the selection.
        return cannot_compute_response;
    }

    const unread_ids = _possible_unread_message_ids(current_filter);

    if (unread_ids === undefined) {
        // _possible_unread_message_ids() only works for certain narrows
        return cannot_compute_response;
    }

    const msg_id = current_filter.first_valid_id_from(unread_ids);

    if (msg_id === undefined) {
        return {
            flavor: "not_found",
        };
    }

    return {
        flavor: "found",
        msg_id,
    };
};

export function rewire_get_first_unread_info(value: typeof get_first_unread_info): void {
    get_first_unread_info = value;
}

export let _possible_unread_message_ids = (
    current_filter: Filter | undefined = filter(),
): number[] | undefined => {
    // This function currently only returns valid results for
    // certain types of narrows, mostly left sidebar narrows.
    // For more complicated narrows we may return undefined.
    //
    // If we do return a result, it will be a subset of unread
    // message ids but possibly a superset of unread message ids
    // that match our filter.
    if (current_filter === undefined) {
        return undefined;
    }

    let sub;
    let topic_name;
    let current_filter_pm_string;

    // For the `with` operator, we can only correctly compute the
    // correct channel/topic for lookup unreads in if we either
    // have the message in our local cache, or we know the filter
    // has already been updated for potentially moved messages.
    //
    // The code path that needs this function is never called in
    // the `with` code path, but for safety, we assert that
    // assumption is not violated.
    //
    // If we need to change that assumption, we can try looking up the
    // target message in message_store, but would need to return
    // undefined if the target message is not available.
    assert(!current_filter.requires_adjustment_for_moved_with_target);

    if (current_filter.can_bucket_by("channel", "topic", "with")) {
        sub = stream_sub(current_filter)!;
        topic_name = topic(current_filter)!;
        return unread.get_msg_ids_for_topic(sub.stream_id, topic_name);
    }

    if (current_filter.can_bucket_by("channel", "topic")) {
        sub = stream_sub(current_filter);
        topic_name = topic(current_filter);
        if (sub === undefined || topic_name === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_topic(sub.stream_id, topic_name);
    }

    if (current_filter.can_bucket_by("channel")) {
        sub = stream_sub(current_filter);
        if (sub === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_stream(sub.stream_id);
    }

    if (current_filter.can_bucket_by("dm", "with") || current_filter.can_bucket_by("dm")) {
        current_filter_pm_string = pm_ids_string(current_filter);
        if (current_filter_pm_string === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_user_ids_string(current_filter_pm_string);
    }

    if (current_filter.can_bucket_by("is-dm")) {
        return unread.get_msg_ids_for_private();
    }

    if (current_filter.can_bucket_by("is-mentioned")) {
        return unread.get_msg_ids_for_mentions();
    }

    if (current_filter.can_bucket_by("is-starred")) {
        return unread.get_msg_ids_for_starred();
    }

    if (current_filter.can_bucket_by("sender")) {
        // TODO: see #9352 to make this more efficient
        return unread.get_all_msg_ids();
    }

    if (current_filter.can_apply_locally()) {
        return unread.get_all_msg_ids();
    }

    return undefined;
};

export function rewire__possible_unread_message_ids(
    value: typeof _possible_unread_message_ids,
): void {
    _possible_unread_message_ids = value;
}

// Are we narrowed to direct messages: the direct message feed or a
// specific direct message conversation.
export function narrowed_to_pms(current_filter: Filter | undefined = filter()): boolean {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.has_operator("dm") || current_filter.has_operand("is", "dm");
}

export function narrowed_by_pm_reply(current_filter: Filter | undefined = filter()): boolean {
    if (current_filter === undefined) {
        return false;
    }
    const terms = current_filter.terms().filter((term) => term.operator !== "with");
    return terms.length === 1 && current_filter.has_operator("dm");
}

export function narrowed_by_topic_reply(current_filter: Filter | undefined = filter()): boolean {
    if (current_filter === undefined) {
        return false;
    }
    const terms = current_filter.terms();
    return (
        terms.length === 2 &&
        current_filter.operands("channel").length === 1 &&
        current_filter.operands("topic").length === 1
    );
}

// We auto-reply under certain conditions, namely when you're narrowed
// to a 1:1 or group direct message conversation, and when you're
// narrowed to some stream/topic pair.
export function narrowed_by_reply(filter?: Filter): boolean {
    return narrowed_by_pm_reply(filter) || narrowed_by_topic_reply(filter);
}

export function narrowed_by_stream_reply(current_filter: Filter | undefined = filter()): boolean {
    if (current_filter === undefined) {
        return false;
    }
    const terms = current_filter.terms();
    return terms.length === 1 && current_filter.operands("channel").length === 1;
}

export function is_for_stream_id(stream_id: number, filter?: Filter): boolean {
    // This is not perfect, since we still track narrows by
    // name, not id, but at least the interface is good going
    // forward.
    const narrow_sub = stream_sub(filter);

    if (narrow_sub === undefined) {
        return false;
    }

    return stream_id === narrow_sub.stream_id;
}
