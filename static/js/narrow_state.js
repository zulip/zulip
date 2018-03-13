var narrow_state = (function () {

var exports = {};

var current_filter;

exports.reset_current_filter = function () {
    current_filter = undefined;
};

exports.set_current_filter = function (filter) {
    current_filter = filter;
};

exports.get_current_filter = function () {
    return current_filter;
};

exports.active = function () {
    return current_filter !== undefined;
};

exports.filter = function () {
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
        return;
    }
    return current_filter.public_operators();
};

exports.search_string = function () {
    return Filter.unparse(exports.operators());
};

// Collect operators which appear only once into an object,
// and discard those which appear more than once.
function collect_single(operators) {
    var seen   = new Dict();
    var result = new Dict();
    _.each(operators, function (elem) {
        var key = elem.operator;
        if (seen.has(key)) {
            result.del(key);
        } else {
            result.set(key, elem.operand);
            seen.set(key, true);
        }
    });
    return result;
}

// Modify default compose parameters (stream etc.) based on
// the current narrowed view.
//
// This logic is here and not in the 'compose' module because
// it will get more complicated as we add things to the narrow
// operator language.
exports.set_compose_defaults = function () {
    var opts = {};
    var single = collect_single(exports.operators());

    // Set the stream, subject, and/or PM recipient if they are
    // uniquely specified in the narrow view.

    if (single.has('stream')) {
        opts.stream = stream_data.get_name(single.get('stream'));
    }

    if (single.has('topic')) {
        opts.subject = single.get('topic');
    }

    if (single.has('pm-with')) {
        opts.private_message_recipient = single.get('pm-with');
    }
    return opts;
};

exports.stream = function () {
    if (current_filter === undefined) {
        return;
    }
    var stream_operands = current_filter.operands("stream");
    if (stream_operands.length === 1) {
        var name = stream_operands[0];

        // Use get_name() to get the most current stream
        // name (considering renames and capitalization).
        return stream_data.get_name(name);
    }
    return;
};

exports.topic = function () {
    if (current_filter === undefined) {
        return;
    }
    var operands = current_filter.operands("topic");
    if (operands.length === 1) {
        return operands[0];
    }
    return;
};

exports.pm_string = function () {
    // If you are narrowed to a PM conversation
    // with users 4, 5, and 99, this will return "4,5,99"

    if (current_filter === undefined) {
        return;
    }

    var operands = current_filter.operands("pm-with");
    if (operands.length !== 1) {
        return;
    }

    var emails_string = operands[0];

    if (!emails_string) {
        return;
    }

    var user_ids_string = people.emails_strings_to_user_ids_string(emails_string);

    return user_ids_string;
};

// Are we narrowed to PMs: all PMs or PMs with particular people.
exports.narrowed_to_pms = function () {
    if (current_filter === undefined) {
        return false;
    }
    return (current_filter.has_operator("pm-with") ||
            current_filter.has_operand("is", "private"));
};

exports.narrowed_by_pm_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    var operators = current_filter.operators();
    return (operators.length === 1 &&
            current_filter.has_operator('pm-with'));
};

exports.narrowed_by_topic_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    var operators = current_filter.operators();
    return (operators.length === 2 &&
            current_filter.operands("stream").length === 1 &&
            current_filter.operands("topic").length === 1);
};

// We auto-reply under certain conditions, namely when you're narrowed
// to a PM (or huddle), and when you're narrowed to some stream/subject pair
exports.narrowed_by_reply = function () {
    return (exports.narrowed_by_pm_reply() ||
            exports.narrowed_by_topic_reply());
};

exports.narrowed_by_stream_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    var operators = current_filter.operators();
    return (operators.length === 1 &&
            current_filter.operands("stream").length === 1);
};

exports.narrowed_to_topic = function () {
    if (current_filter === undefined) {
        return false;
    }
    return (current_filter.has_operator("stream") &&
            current_filter.has_operator("topic"));
};

exports.narrowed_to_search = function () {
    return (current_filter !== undefined) && current_filter.is_search();
};

exports.muting_enabled = function () {
    return (!exports.narrowed_to_topic() && !exports.narrowed_to_search() &&
            !exports.narrowed_to_pms());
};

exports.is_for_stream_id = function (stream_id) {
    // This is not perfect, since we still track narrows by
    // name, not id, but at least the interface is good going
    // forward.
    var sub = stream_data.get_sub_by_id(stream_id);

    if (sub === undefined) {
        blueslip.error('Bad stream id ' + stream_id);
        return false;
    }

    var narrow_stream_name = exports.stream();

    if (narrow_stream_name === undefined) {
        return false;
    }

    return (sub.name === narrow_stream_name);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = narrow_state;
}
