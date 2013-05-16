var narrow = (function () {

var exports = {};

function Filter(operators) {
    if (operators === undefined) {
        this._operators = [];
    } else {
        this._operators = this._canonicalize_operators(operators);
    }
}

Filter.prototype = {
    predicate: function Filter_predicate() {
        if (this._predicate === undefined) {
            this._predicate = this._build_predicate();
        }
        return this._predicate;
    },

    operators: function Filter_operators() {
        return this._operators;
    },

    public_operators: function Filter_public_operators() {
        var safe_to_return;
        safe_to_return = [];
        $.each(this._operators, function (index, value) {
            // Currently just filter out the "in" keyword.
            if (value[0] !== "in") {
                safe_to_return.push(value);
            }
        });
        if (safe_to_return.length !== 0) {
            return safe_to_return;
        }
    },

    operands: function Filter_get_operands(operator) {
        var result = [];
        $.each(this._operators, function (idx, elem) {
            if (elem[0] === operator) {
                result.push(elem[1]);
            }
        });
        return result;
    },

    is_search: function Filter_is_search() {
        var retval = false;
        $.each(this._operators, function (idx, elem) {
            if (elem[0] === "search") {
                retval = true;
                return false;
            }});
        return retval;
    },

    can_apply_locally: function Filter_can_apply_locally() {
        return ! this.is_search();
    },

    _canonicalize_operators: function Filter__canonicalize_operators(operators_mixed_case) {
        var new_operators = [];
        // We don't use $.map because it flattens returned arrays.
        $.each(operators_mixed_case, function (idx, operator) {
            // We may want to consider allowing mixed-case operators at some point
            new_operators.push([operator[0], subs.canonicalized_name(operator[1])]);
        });
        return new_operators;
    },

    // Build a filter function from a list of operators.
    _build_predicate: function Filter__build_predicate() {
        var operators = this._operators;

        if (! this.can_apply_locally()) {
            return function () { return true; };
        }

        // FIXME: This is probably pretty slow.
        // We could turn it into something more like a compiler:
        // build JavaScript code in a string and then eval() it.

        return function (message) {
            var operand, i;
            for (i = 0; i < operators.length; i++) {
                operand = operators[i][1];
                switch (operators[i][0]) {
                case 'is':
                    if (operand === 'private-message') {
                        if (message.type !== 'private')
                            return false;
                    } else if (operand === 'starred') {
                        if (!message.starred) {
                            return false;
                        }
                    } else if (operand === 'mentioned') {
                        if (!message.mentioned) {
                            return false;
                        }
                    }

                    break;

                case 'in':
                    if (operand === 'home') {
                        return exports.message_in_home(message);
                    }
                    else if (operand === 'all') {
                        return true;
                    }
                    break;

                case 'stream':
                    if ((message.type !== 'stream') ||
                        (message.stream.toLowerCase() !== operand))
                        return false;
                    break;

                case 'subject':
                    if ((message.type !== 'stream') ||
                        (message.subject.toLowerCase() !== operand))
                        return false;
                    break;

                case 'sender':
                    if ((message.sender_email.toLowerCase() !== operand))
                        return false;
                    break;

                case 'pm-with':
                    if ((message.type !== 'private') ||
                        message.reply_to.toLowerCase() !== operand.split(',').sort().join(','))
                        return false;
                    break;
                }
            }

            // All filters passed.
            return true;
        };
    }
};

exports.Filter = Filter;

var current_filter;

exports.active = function () {
    return current_filter !== undefined;
};

exports.filter = function () {
    return current_filter;
};

exports.predicate = function () {
    if (current_filter === undefined) {
        return function () { return true; };
    }
    return current_filter.predicate();
};

exports.operators = function () {
    if (current_filter === undefined) {
        return false;
    }
    return current_filter.operators();
};

/* Operators we should send to the server. */
exports.public_operators = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    return current_filter.public_operators();
};

/* We use a variant of URI encoding which looks reasonably
   nice and still handles unambiguously cases such as
   spaces in operands.

   This is just for the search bar, not for saving the
   narrow in the URL fragment.  There we do use full
   URI encoding to avoid problematic characters. */
function encodeOperand(operand) {
    return operand.replace(/%/g,  '%25')
                  .replace(/\+/g, '%2B')
                  .replace(/ /g,  '+');
}

function decodeOperand(encoded) {
    return util.robust_uri_decode(encoded.replace(/\+/g, ' '));
}

/* Convert a list of operators to a string.
   Each operator is a key-value pair like

       ['subject', 'my amazing subject']

   These are not keys in a JavaScript object, because we
   might need to support multiple operators of the same type.
*/
function unparse(operators) {
    var parts = [];
    $.each(operators, function (index, elem) {
        var operator = elem[0];
        if (operator === 'search') {
            // Search terms are the catch-all case.
            // All tokens that don't start with a known operator and
            // a colon are glued together to form a search term.
            parts.push(elem[1]);
        } else {
            parts.push(elem[0] + ':' + encodeOperand(elem[1].toString().toLowerCase()));
        }
    });
    return parts.join(' ');
}

// Convert a list of operators to a human-readable description.
exports.describe = function (operators) {
    return $.map(operators, function (elem) {
        var operand = elem[1];
        switch (elem[0]) {
        case 'is':
            if (operand === 'private-message') {
                return 'Narrow to all private messages';
            } else if (operand === 'starred') {
                return 'Narrow to starred messages';
            } else if (operand === 'mentioned') {
                return 'Narrow to mentioned messages';
            }
            break;

        case 'stream':
            return 'Narrow to stream ' + operand;

        case 'subject':
            return 'Narrow to subject ' + operand;

        case 'sender':
            return 'Narrow to sender ' + operand;

        case 'pm-with':
            return 'Narrow to private messages with ' + operand;

        case 'search':
            return 'Search for ' + operand;

        case 'in':
            return 'Narrow to messages in ' + operand;
        }
        return 'Narrow to (unknown operator)';
    }).join(', ');
};

// Collect operators which appear only once into an object,
// and discard those which appear more than once.
function collect_single(operators) {
    var seen   = {};
    var result = {};
    $.each(operators, function (index, elem) {
        var key = elem[0];
        if (seen.hasOwnProperty(key)) {
            delete result[key];
        } else {
            result[key] = elem[1];
            seen  [key] = true;
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
exports.set_compose_defaults = function (opts) {
    var single = collect_single(exports.operators());

    // Set the stream, subject, and/or PM recipient if they are
    // uniquely specified in the narrow view.
    $.each(['stream', 'subject'], function (idx, key) {
        if (single[key] !== undefined)
            opts[key] = single[key];
    });

    if (single['pm-with'] !== undefined)
        opts.private_message_recipient = single['pm-with'];
};

// Parse a string into a list of operators (see below).
exports.parse = function (str) {
    var operators   = [];
    var search_term = [];
    var matches = str.match(/"[^"]+"|\S+/g);
    if (matches === null) {
        return operators;
    }
    $.each(matches, function (idx, token) {
        var parts, operator;
        if (token.length === 0)
            return;
        parts = token.split(':');
        if (token[0] === '"' || parts.length === 1) {
            // Looks like a normal search term.
            search_term.push(token);
        } else {
            // Looks like an operator.
            // FIXME: Should we skip unknown operator names here?
            operator = parts.shift();
            operators.push([operator, decodeOperand(parts.join(':'))]);
        }
    });
    // NB: Callers of 'parse' can assume that the 'search' operator is last.
    if (search_term.length > 0)
        operators.push(['search', search_term.join(' ')]);
    return operators;
};

exports.stream_in_home = function (stream_name) {
    // If we don't know about this stream for some reason,
    // we might not have loaded the in_home_view information
    // yet so show it
    var stream = subs.have(stream_name);
    if (stream) {
        return stream.in_home_view;
    } else {
        return true;
    }
};

exports.message_in_home = function (message) {
    if (message.type === "private") {
        return true;
    }

    return exports.stream_in_home(message.stream);
};

exports.stream = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    var j;
    var current_operators = current_filter.operators();
    for (j = 0; j < current_operators.length; j++) {
        if (current_operators[j][0] === "stream") {
            return current_operators[j][1];
        }
    }
    return undefined;
};

exports.activate = function (operators, opts) {
    opts = $.extend({}, {
        then_select_id: home_msg_list.selected_id(),
        select_first_unread: false,
        change_hash: true,
        trigger: 'unknown'
    }, opts);

    if (opts.then_select_id === -1) {
        // If we're loading the page via a narrowed URL, we may not
        // have setup the home view yet.  In that case, use the
        // initial pointer.  We can remove this code if we later move
        // to a model where home_msg_list.selected_id() is always
        // initialized early.
        opts.then_select_id = page_params.initial_pointer;
    }

    // Unfade the home view before we switch tables.
    compose.unfade_messages();

    var was_narrowed = exports.active();
    var then_select_id  = opts.then_select_id;

    current_filter = new Filter(operators);

    var collapse_messages = true;
    $.each(operators, function (idx, operator) {
        if (operator[0].toString().toLowerCase() === 'search') {
            collapse_messages = false;
            return false;
        }
    });

    narrowed_msg_list = new MessageList('zfilt', current_filter,
                                        {collapse_messages: collapse_messages});
    current_msg_list = narrowed_msg_list;

    function maybe_select_closest() {
        if (! narrowed_msg_list.empty()) {
            if (opts.select_first_unread) {
                then_select_id = narrowed_msg_list.last().id;
                $.each(narrowed_msg_list.all(), function (idx, msg) {
                    if (unread.message_unread(msg)) {
                        then_select_id = msg.id;
                        return false;
                    }
                });
            }
            narrowed_msg_list.select_id(then_select_id, {then_scroll: true, use_closest: true});
        }
    }

    // Don't bother populating a message list when it won't contain
    // the message we want anyway or if the filter can't be applied
    // locally.
    if (all_msg_list.get(then_select_id) !== undefined && current_filter.can_apply_locally()) {
        add_messages(all_msg_list.all(), narrowed_msg_list);
    }

    var defer_selecting_closest = narrowed_msg_list.empty();
    load_old_messages({
        anchor: then_select_id,
        num_before: 200,
        num_after: 200,
        msg_list: narrowed_msg_list,
        cont: function (messages) {
            if (defer_selecting_closest) {
                maybe_select_closest();
            }
        },
        cont_will_add_messages: false
    });

    // Show the new set of messages.
    $("#main_div").addClass("narrowed_view");
    $("#zfilt").addClass("focused_table");
    $("#zhome").removeClass("focused_table");
    $("#zfilt").css("opacity", 0).animate({opacity: 1});

    // Deal with message condensing/uncondensing.
    // In principle, this code causes us to scroll around because divs
    // above us could change size -- which is problematic, because it
    // could cause us to lose our position. But doing this here, right
    // after showing the table, seems to cause us to win the race.
    $("tr.message_row").each(ui.process_condensing);

    reset_load_more_status();
    if (! defer_selecting_closest) {
        maybe_select_closest();
    }

    function extract_search_terms(operators) {
        var i = 0;
        for (i = 0; i < operators.length; i++) {
            var type = operators[i][0];
            if (type === "search") {
                return operators[i][1];
            }
        }
        return undefined;
    }

    // Put the narrow operators in the URL fragment.
    // Disabled when the URL fragment was the source
    // of this narrow.
    if (opts.change_hash)
        hashchange.save_narrow(operators);

    // Put the narrow operators in the search bar.
    $('#search_query').val(unparse(operators));
    search.update_button_visibility();
    compose.update_recipient_on_narrow();
    compose.update_faded_messages();

    $(document).trigger($.Event('narrow_activated.zephyr', {msg_list: narrowed_msg_list,
                                                            filter: current_filter,
                                                            trigger: opts.trigger}));
};

// Activate narrowing with a single operator.
// This is just for syntactic convenience.
exports.by = function (operator, operand, opts) {
    exports.activate([[operator, operand]], opts);
};

exports.by_subject = function (target_id, opts) {
    var original = current_msg_list.get(target_id);
    if (original.type !== 'stream') {
        // Only stream messages have subjects, but the
        // user wants us to narrow in some way.
        exports.by_recipient(target_id, opts);
        return;
    }
    opts = $.extend({}, {then_select_id: target_id}, opts);
    exports.activate([
            ['stream',  original.stream],
            ['subject', original.subject]
        ], opts);
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function (target_id, opts) {
    opts = $.extend({}, {then_select_id: target_id}, opts);
    var message = current_msg_list.get(target_id);
    switch (message.type) {
    case 'private':
        exports.by('pm-with', message.reply_to, opts);
        break;

    case 'stream':
        exports.by('stream', message.stream, opts);
        break;
    }
};

exports.by_time_travel = function (target_id, opts) {
    opts = $.extend({}, {then_select_id: target_id}, opts);
    narrow.activate([], opts);
};

exports.deactivate = function () {
    if (current_filter === undefined) {
        return;
    }

    current_filter = undefined;

    exports.hide_empty_narrow_message();

    $("#main_div").removeClass('narrowed_view');
    $("#searchbox").removeClass('narrowed_view');
    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');
    $("#zhome").css("opacity", 0).animate({opacity: 1});

    $('#search_query').val('');
    reset_load_more_status();

    current_msg_list = home_msg_list;
    // We fall back to the closest selected id, if the user has removed a stream from the home
    // view since leaving it the old selected id might no longer be there
    home_msg_list.select_id(home_msg_list.selected_id(), {then_scroll: true, use_closest: true});

    hashchange.save_narrow();

    // This really shouldn't be necessary since the act of unnarrowing
    // fires a "message_selected.zephyr" event that in principle goes
    // and takes care of this, but on Safari (at least) there
    // seems to be some sort of order-of-events issue that causes
    // the scrolling not to happen, so this is my hack for now.
    scroll_to_selected();

    $(document).trigger($.Event('narrow_deactivated.zephyr', {msg_list: current_msg_list}));
};

exports.restore_home_state = function() {
    // If we click on the Home link while already at Home, unnarrow.
    // If we click on the Home link from another nav pane, just go
    // back to the state you were in (possibly still narrowed) before
    // you left the Home pane.
    if (!ui.home_tab_obscured()) {
        exports.deactivate();
    }
    maybe_scroll_to_selected();
};

function pick_empty_narrow_banner() {
    var default_banner = $('#empty_narrow_message');
    if (current_filter === undefined) {
        return default_banner;
    }

    var first_operator = current_filter.operators()[0][0];
    var first_operand = current_filter.operators()[0][1];

    if (first_operator === "is") {
        if (first_operand === "starred") {
            // You have no starred messages.
            return $("#empty_star_narrow_message");
        } else if (first_operand === "mentioned") {
            return $("#empty_narrow_all_mentioned");
        } else if (first_operand === "private-message") {
            // You have no private messages.
            return $("#empty_narrow_all_private_message");
        }
    } else if ((first_operator === "stream") && !subs.have(first_operand)) {
        // You are narrowed to a stream to which you aren't subscribed.
        return $("#nonsubbed_stream_narrow_message");
    } else if (first_operator === "search") {
        // You are narrowed to empty search results.
        return $("#empty_search_narrow_message");
    } else if (first_operator === "pm-with") {
        if (first_operand.indexOf(',') === -1) {
            // You have no private messages with this person
            return $("#empty_narrow_private_message");
        } else {
            return $("#empty_narrow_multi_private_message");
        }
    }
    return default_banner;
}

exports.show_empty_narrow_message = function () {
    $(".empty_feed_notice").hide();
    pick_empty_narrow_banner().show();
};

exports.hide_empty_narrow_message = function () {
    $(".empty_feed_notice").hide();
};

exports.by_stream_uri = function (stream) {
    return "#narrow/stream/" + hashchange.encodeHashComponent(stream);
};

exports.by_stream_subject_uri = function (stream, subject) {
    return "#narrow/stream/" + hashchange.encodeHashComponent(stream) +
           "/subject/" + hashchange.encodeHashComponent(subject);
};

exports.narrowed_to_pms = function () {
    // Are we narrowed to PMs: all PMs or PMs with particular people.
    var operators = narrow.operators();
    if (!operators) {
        return false;
    }
    if ((operators[0][0] === "pm-with") ||
        ((operators[0][0] === "is") && (operators[0][1] === "private-message"))) {
        return true;
    }
    return false;
};

// We auto-reply under certain conditions, namely when you're narrowed
// to a PM (or huddle), and when you're narrowed to some stream/subject pair
exports.narrowed_by_reply = function () {
    if (narrow.filter() === undefined) {
        return false;
    }
    var operators = narrow.filter().operators();
        return ((operators.length === 1 &&
                 operators[0][0] === "pm-with") ||
                (operators.length === 2 &&
                 operators[0][0] === "stream" &&
                 operators[1][0] === "subject"));
};

return exports;

}());
