import assert from "minimalistic-assert";

import {Filter} from "./filter.ts";
import * as inbox_util from "./inbox_util.ts";
import * as message_lists from "./message_lists.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {NarrowTerm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import type {StreamSubscription} from "./sub_store.ts";
import * as unread from "./unread.ts";

export function filter(): Filter | undefined {
    // We use Filter objects for message views as well as the list of
    // topics channel view.
    //
    // TODO: Some renaming/refactoring to put this in a separate
    // module from the rest of this file, which is all about message
    // views, would be valuable.
    if (inbox_util.is_visible()) {
        return inbox_util.filter;
    }

    // `Recent Conversations` returns undefined;
    return message_lists.current?.data.filter;
}

export function search_terms(current_filter: Filter | undefined = filter()): NarrowTerm[] {
    if (current_filter === undefined) {
        if (page_params.narrow !== undefined) {
            current_filter = new Filter(page_params.narrow);
        } else {
            current_filter = new Filter([]);
        }
    }

    const non_search_operators = new Set(["with"]);

    return current_filter.terms().filter((term) => !non_search_operators.has(term.operator));
}

export function is_search_view(current_filter: Filter | undefined = filter()): boolean {
    if (current_filter && !current_filter.contains_no_partial_conversations()) {
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
    private_message_recipient_ids?: number[];
} {
    const opts: {stream_id?: number; topic?: string; private_message_recipient_ids?: number[]} = {};
    const single = collect_single(search_terms());

    // Set the stream, topic, and/or direct message recipient
    // if they are uniquely specified in the narrow view.

    if (single.has("channel")) {
        // Only set opts.stream_id if it is a valid stream ID.
        const narrow_stream_id = stream_id(filter(), true);
        if (narrow_stream_id !== undefined) {
            opts.stream_id = narrow_stream_id;
        }
    }

    const topic = single.get("topic");
    if (topic !== undefined) {
        opts.topic = topic;
    }

    const private_message_recipient_emails = single.get("dm");
    if (
        private_message_recipient_emails !== undefined &&
        people.is_valid_bulk_emails_for_compose(private_message_recipient_emails.split(","))
    ) {
        opts.private_message_recipient_ids = people.emails_string_to_user_ids(
            private_message_recipient_emails,
        );
    }
    return opts;
}

export let stream_id = (
    current_filter: Filter | undefined = filter(),
    // If true, we'll return undefined if the filter contains a
    // stream_id, but that stream ID is not present in stream_data
    // (whether because it's an invalid channel ID, or because the
    // channel is not accessible to this user).
    only_valid_id = false,
): number | undefined => {
    if (current_filter === undefined) {
        return undefined;
    }
    const stream_operands = current_filter.operands("channel");
    if (stream_operands.length === 1 && stream_operands[0] !== undefined) {
        const id = Number.parseInt(stream_operands[0], 10);
        if (!Number.isNaN(id)) {
            return only_valid_id ? stream_data.get_sub_by_id(id)?.stream_id : id;
        }
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
    return stream_data.get_sub_by_id(id)?.name;
}

export function stream_sub(
    current_filter: Filter | undefined = filter(),
): StreamSubscription | undefined {
    const id = stream_id(current_filter);
    if (id === undefined) {
        return undefined;
    }
    return stream_data.get_sub_by_id(id);
}

export function topic(current_filter: Filter | undefined = filter()): string | undefined {
    if (current_filter === undefined) {
        return undefined;
    }
    const operands = current_filter.operands("topic");
    if (operands.length === 1) {
        return operands[0];
    }
    return undefined;
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

export function pm_ids_set(filter?: Filter): Set<number> {
    const ids_string = pm_ids_string(filter);
    const pm_ids_list = ids_string ? people.user_ids_string_to_ids_array(ids_string) : [];
    return new Set(pm_ids_list);
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

// We expect get_first_unread_info and therefore _possible_unread_message_ids
// to always be called with a filter from a message list.
export let get_first_unread_info = (
    message_list_filter: Filter,
): {flavor: "cannot_compute" | "not_found"} | {flavor: "found"; msg_id: number} => {
    const cannot_compute_response: {flavor: "cannot_compute"} = {flavor: "cannot_compute"};
    if (!message_list_filter.can_apply_locally()) {
        // For things like search queries, where the server has info
        // that the client isn't privy to, we need to wait for the
        // server to give us a definitive list of messages before
        // deciding where we'll move the selection.
        return cannot_compute_response;
    }

    const unread_ids = _possible_unread_message_ids(message_list_filter);

    if (unread_ids === undefined) {
        // _possible_unread_message_ids() only works for certain narrows
        return cannot_compute_response;
    }

    const msg_id = message_list_filter.first_valid_id_from(unread_ids);

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

export let _possible_unread_message_ids = (message_list_filter: Filter): number[] | undefined => {
    // This function currently only returns valid results for
    // certain types of narrows, mostly left sidebar narrows.
    // For more complicated narrows we may return undefined.
    //
    // If we do return a result, it will be a subset of unread
    // message ids but possibly a superset of unread message ids
    // that match our filter.
    let filter_stream_id: number | undefined;
    let topic_name: string | undefined;
    let filter_pm_string: string | undefined;

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
    assert(!message_list_filter.requires_adjustment_for_moved_with_target);

    if (
        message_list_filter.can_bucket_by("channel", "topic", "with") ||
        message_list_filter.can_bucket_by("channel", "topic")
    ) {
        filter_stream_id = stream_id(message_list_filter, true);
        topic_name = topic(message_list_filter);
        if (filter_stream_id === undefined || topic_name === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_topic(filter_stream_id, topic_name);
    }

    if (message_list_filter.can_bucket_by("channel")) {
        filter_stream_id = stream_id(message_list_filter, true);
        if (filter_stream_id === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_stream(filter_stream_id);
    }

    if (
        message_list_filter.can_bucket_by("dm", "with") ||
        message_list_filter.can_bucket_by("dm")
    ) {
        filter_pm_string = pm_ids_string(message_list_filter);
        if (filter_pm_string === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_user_ids_string(filter_pm_string);
    }

    if (message_list_filter.can_bucket_by("is-dm")) {
        return unread.get_msg_ids_for_private();
    }

    if (message_list_filter.can_bucket_by("is-mentioned")) {
        return unread.get_msg_ids_for_mentions();
    }

    if (message_list_filter.can_bucket_by("is-starred")) {
        return unread.get_msg_ids_for_starred();
    }

    if (message_list_filter.can_bucket_by("sender")) {
        // TODO: see #9352 to make this more efficient
        return unread.get_all_msg_ids();
    }

    if (message_list_filter.can_apply_locally()) {
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
    const terms = current_filter.terms().filter((term) => term.operator !== "with");
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

export function narrowed_to_stream_id(stream_id_to_check: number, filter?: Filter): boolean {
    const current_stream_id = stream_id(filter);
    if (current_stream_id === undefined) {
        return false;
    }
    return stream_id_to_check === current_stream_id;
}
