"use strict";

const people = require("./people");

let current_filter;

exports.reset_current_filter = function () {
    current_filter = undefined;
};

exports.set_current_filter = function (filter) {
    current_filter = filter;
};

exports.active = function () {
    return current_filter !== undefined;
};

exports.filter = function () {
    // Both, `All messages` and
    // `Recent topics` have `current_filter=undefined`
    return current_filter;
};

exports.operators = function () {
    if (current_filter === undefined) {
        return new Filter(page_params.narrow).operators();
    }
    return current_filter.operators();
};

exports.update_email = function (user_id, new_email) {
    if (current_filter !== undefined) {
        current_filter.update_email(user_id, new_email);
    }
};

/* Operators we should send to the server. */
exports.public_operators = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    return current_filter.public_operators();
};

exports.search_string = function () {
    return Filter.unparse(exports.operators());
};

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
exports.set_compose_defaults = function () {
    const opts = {};
    const single = collect_single(exports.operators());

    // Set the stream, topic, and/or PM recipient if they are
    // uniquely specified in the narrow view.

    if (single.has("stream")) {
        opts.stream = stream_data.get_name(single.get("stream"));
    }

    if (single.has("topic")) {
        opts.topic = single.get("topic");
    }

    if (single.has("pm-with")) {
        const private_message_recipient = single.get("pm-with");
        if (people.is_valid_bulk_emails_for_compose(private_message_recipient.split(","))) {
            opts.private_message_recipient = private_message_recipient;
        }
    }
    return opts;
};

exports.stream = function () {
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
};

exports.stream_sub = function () {
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
};

exports.topic = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    const operands = current_filter.operands("topic");
    if (operands.length === 1) {
        return operands[0];
    }
    return undefined;
};

exports.pm_string = function () {
    // If you are narrowed to a PM conversation
    // with users 4, 5, and 99, this will return "4,5,99"

    if (current_filter === undefined) {
        return undefined;
    }

    const operands = current_filter.operands("pm-with");
    if (operands.length !== 1) {
        return undefined;
    }

    const emails_string = operands[0];

    if (!emails_string) {
        return undefined;
    }

    const user_ids_string = people.reply_to_to_user_ids_string(emails_string);

    return user_ids_string;
};

exports.get_first_unread_info = function () {
    if (current_filter === undefined) {
        // we don't yet support the all-messages view
        blueslip.error("unexpected call to get_first_unread_info");
        return {
            flavor: "cannot_compute",
        };
    }

    if (!current_filter.can_apply_locally()) {
        // For things like search queries, where the server has info
        // that the client isn't privvy to, we need to wait for the
        // server to give us a definitive list of messages before
        // deciding where we'll move the selection.
        return {
            flavor: "cannot_compute",
        };
    }

    const unread_ids = exports._possible_unread_message_ids();

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
};

exports._possible_unread_message_ids = function () {
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
        sub = exports.stream_sub();
        if (sub === undefined) {
            return [];
        }
        topic_name = exports.topic();
        return unread.get_msg_ids_for_topic(sub.stream_id, topic_name);
    }

    if (current_filter.can_bucket_by("stream")) {
        sub = exports.stream_sub();
        if (sub === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_stream(sub.stream_id);
    }

    if (current_filter.can_bucket_by("pm-with")) {
        current_filter_pm_string = exports.pm_string();
        if (current_filter_pm_string === undefined) {
            return [];
        }
        return unread.get_msg_ids_for_person(current_filter_pm_string);
    }

    if (current_filter.can_bucket_by("is-private")) {
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

// Are we narrowed to PMs: all PMs or PMs with particular people.
exports.narrowed_to_pms = function () {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.has_operator("pm-with") || current_filter.has_operand("is", "private");
};

exports.narrowed_by_pm_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    const operators = current_filter.operators();
    return operators.length === 1 && current_filter.has_operator("pm-with");
};

exports.narrowed_by_topic_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    const operators = current_filter.operators();
    return (
        operators.length === 2 &&
        current_filter.operands("stream").length === 1 &&
        current_filter.operands("topic").length === 1
    );
};

// We auto-reply under certain conditions, namely when you're narrowed
// to a PM (or huddle), and when you're narrowed to some stream/topic pair
exports.narrowed_by_reply = function () {
    return exports.narrowed_by_pm_reply() || exports.narrowed_by_topic_reply();
};

exports.narrowed_by_stream_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    const operators = current_filter.operators();
    return operators.length === 1 && current_filter.operands("stream").length === 1;
};

exports.narrowed_to_topic = function () {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.has_operator("stream") && current_filter.has_operator("topic");
};

exports.narrowed_to_search = function () {
    return current_filter !== undefined && current_filter.is_search();
};

exports.narrowed_to_starred = function () {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.has_operand("is", "starred");
};

exports.muting_enabled = function () {
    return (
        !exports.narrowed_to_topic() &&
        !exports.narrowed_to_search() &&
        !exports.narrowed_to_pms() &&
        !exports.narrowed_to_starred()
    );
};

exports.is_for_stream_id = function (stream_id) {
    // This is not perfect, since we still track narrows by
    // name, not id, but at least the interface is good going
    // forward.
    const narrow_sub = exports.stream_sub();

    if (narrow_sub === undefined) {
        return false;
    }

    return stream_id === narrow_sub.stream_id;
};

window.narrow_state = exports;
