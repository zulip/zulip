import * as blueslip from "./blueslip";
import {Filter} from "./filter";
import * as inbox_util from "./inbox_util";
import {page_params} from "./page_params";
import * as people from "./people";
import * as recent_view_util from "./recent_view_util";
import * as stream_data from "./stream_data";
import * as unread from "./unread";

let current_filter;

export function reset_current_filter() {
    current_filter = undefined;
}

export function set_current_filter(filter) {
    current_filter = filter;
}

export function active() {
    return current_filter !== undefined;
}

export function filter() {
    // Both, `All messages` and
    // `Recent Conversations` have `current_filter=undefined`
    return current_filter;
}

export function operators() {
    if (current_filter === undefined) {
        return new Filter(page_params.narrow).operators();
    }
    return current_filter.operators();
}

export function is_message_feed_visible() {
    return !recent_view_util.is_visible() && !inbox_util.is_visible();
}

export function update_email(user_id, new_email) {
    if (current_filter !== undefined) {
        current_filter.update_email(user_id, new_email);
    }
}

/* Operators we should send to the server. */
export function public_operators() {
    if (current_filter === undefined) {
        return undefined;
    }
    return current_filter.public_operators();
}

export function search_string() {
    return Filter.unparse(operators());
}

// Collect operators which appear only once into an object,
// and discard those which appear more than once.
function collect_single(operators) {
    const seen = new Map();
    const result = new Map();

    for (const elem of operators) {
        const key = elem.operator;
        if (seen.has(key)) {
            result.delete(key);
        } else {
            result.set(key, elem.operand);
            seen.set(key, true);
        }
    }

    return result;
}

// Modify default compose parameters (stream etc.) based on
// the current narrowed view.
//
// This logic is here and not in the 'compose' module because
// it will get more complicated as we add things to the narrow
// operator language.
export function set_compose_defaults() {
    const opts = {};
    const single = collect_single(operators());

    // Set the stream, topic, and/or direct message recipient
    // if they are uniquely specified in the narrow view.

    if (single.has("stream")) {
        // The raw stream name from collect_single may be an arbitrary
        // unvalidated string from the URL fragment and thus not be valid.
        // So we look up the resolved stream and return that if appropriate.
        const sub = stream_sub();
        if (sub !== undefined) {
            opts.stream_id = sub.stream_id;
        }
    }

    if (single.has("topic")) {
        opts.topic = single.get("topic");
    }

    if (single.has("dm")) {
        const private_message_recipient = single.get("dm");
        if (people.is_valid_bulk_emails_for_compose(private_message_recipient.split(","))) {
            opts.private_message_recipient = private_message_recipient;
        }
    }
    return opts;
}

export function stream_name() {
    if (current_filter === undefined) {
        return undefined;
    }
    const stream_operands = current_filter.operands("stream");
    if (stream_operands.length === 1) {
        const name = stream_operands[0];

        // Use get_name() to get the most current stream
        // name (considering renames and capitalization).
        return stream_data.get_name(name);
    }
    return undefined;
}

export function stream_sub() {
    if (current_filter === undefined) {
        return undefined;
    }
    const stream_operands = current_filter.operands("stream");
    if (stream_operands.length !== 1) {
        return undefined;
    }

    const name = stream_operands[0];
    const sub = stream_data.get_sub_by_name(name);

    return sub;
}

export function topic() {
    if (current_filter === undefined) {
        return undefined;
    }
    const operands = current_filter.operands("topic");
    if (operands.length === 1) {
        return operands[0];
    }
    return undefined;
}

export function pm_ids_string() {
    // If you are narrowed to a group direct message with
    // users 4, 5, and 99, this will return "4,5,99"
    const emails_string = pm_emails_string();

    if (!emails_string) {
        return undefined;
    }

    const user_ids_string = people.reply_to_to_user_ids_string(emails_string);

    return user_ids_string;
}

export function pm_emails_string() {
    if (current_filter === undefined) {
        return undefined;
    }

    const operands = current_filter.operands("dm");
    if (operands.length !== 1) {
        return undefined;
    }

    return operands[0];
}

export function get_first_unread_info() {
    if (current_filter === undefined) {
        // we don't yet support the all-messages view
        blueslip.error("unexpected call to get_first_unread_info");
        return {
            flavor: "cannot_compute",
        };
    }

    if (!current_filter.can_apply_locally()) {
        // For things like search queries, where the server has info
        // that the client isn't privy to, we need to wait for the
        // server to give us a definitive list of messages before
        // deciding where we'll move the selection.
        return {
            flavor: "cannot_compute",
        };
    }

    const unread_ids = _possible_unread_message_ids();

    if (unread_ids === undefined) {
        // _possible_unread_message_ids() only works for certain narrows
        return {
            flavor: "cannot_compute",
        };
    }

    const msg_id = current_filter.first_valid_id_from(unread_ids);

    if (msg_id === undefined) {
        return {
            flavor: "not_found",
        };
    }

    return {
        flavor: "found",
        msg_id: unread_ids[0],
    };
}

export function _possible_unread_message_ids() {
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

    if (current_filter.can_bucket_by("stream", "topic")) {
        sub = stream_sub();
        if (sub === undefined) {
            return [];
        }
        topic_name = topic();
        return unread.get_msg_ids_for_topic(sub.stream_id, topic_name);
    }

    if (current_filter.can_bucket_by("stream")) {
        sub = stream_sub();
        if (sub === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_stream(sub.stream_id);
    }

    if (current_filter.can_bucket_by("dm")) {
        current_filter_pm_string = pm_ids_string();
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
}

// Are we narrowed to direct messages: all direct messages
// or direct messages with particular people.
export function narrowed_to_pms() {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.has_operator("dm") || current_filter.has_operand("is", "dm");
}

export function narrowed_by_pm_reply() {
    if (current_filter === undefined) {
        return false;
    }
    const operators = current_filter.operators();
    return operators.length === 1 && current_filter.has_operator("dm");
}

export function narrowed_by_topic_reply() {
    if (current_filter === undefined) {
        return false;
    }
    const operators = current_filter.operators();
    return (
        operators.length === 2 &&
        current_filter.operands("stream").length === 1 &&
        current_filter.operands("topic").length === 1
    );
}

// We auto-reply under certain conditions, namely when you're narrowed
// to a 1:1 or group direct message conversation, and when you're
// narrowed to some stream/topic pair.
export function narrowed_by_reply() {
    return narrowed_by_pm_reply() || narrowed_by_topic_reply();
}

export function narrowed_by_stream_reply() {
    if (current_filter === undefined) {
        return false;
    }
    const operators = current_filter.operators();
    return operators.length === 1 && current_filter.operands("stream").length === 1;
}

export function narrowed_to_topic() {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.has_operator("stream") && current_filter.has_operator("topic");
}

export function narrowed_to_search() {
    return current_filter !== undefined && current_filter.is_search();
}

export function narrowed_to_starred() {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.has_operand("is", "starred");
}

export function excludes_muted_topics() {
    return (
        !narrowed_to_topic() &&
        !narrowed_to_search() &&
        !narrowed_to_pms() &&
        !narrowed_to_starred()
    );
}

export function is_for_stream_id(stream_id) {
    // This is not perfect, since we still track narrows by
    // name, not id, but at least the interface is good going
    // forward.
    const narrow_sub = stream_sub();

    if (narrow_sub === undefined) {
        return false;
    }

    return stream_id === narrow_sub.stream_id;
}
