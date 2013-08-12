var narrow = (function () {

var exports = {};

function Filter(operators) {
    if (operators === undefined) {
        this._operators = [];
    } else {
        this._operators = this._canonicalize_operators(operators);
    }
}

var canonical_operators = {"from": "sender", "subject": "topic"};

exports.canonicalize_operator = function (operator) {
    operator = operator.toLowerCase();
    if (canonical_operators.hasOwnProperty(operator)) {
        return canonical_operators[operator];
    } else {
        return operator;
    }
};

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
        var safe_to_return = _.filter(this._operators, function (value) {
            // Currently just filter out the "in" keyword.
            return value[0] !== 'in';
        });
        if (safe_to_return.length !== 0) {
            return safe_to_return;
        }
    },

    operands: function Filter_get_operands(operator) {
        return _.chain(this._operators)
            .filter(function (elem) { return elem[0] === operator; })
            .map(function (elem) { return elem[1]; })
            .value();
    },

    has_operand: function Filter_has_operand(operator, operand) {
        return _.any(this._operators, function (elem) {
            return elem[0] === operator && elem[1] === operand;
        });
    },

    has_operator: function Filter_has_operator(operator) {
        return _.any(this._operators, function (elem) {
            return elem[0] === operator;
        });
    },

    is_search: function Filter_is_search() {
        return this.has_operator('search');
    },

    can_apply_locally: function Filter_can_apply_locally() {
        return ! this.is_search();
    },

    _canonicalize_operators: function Filter__canonicalize_operators(operators_mixed_case) {
        return _.map(operators_mixed_case, function (operator) {
            // We may want to consider allowing mixed-case operators at some point
            return [exports.canonicalize_operator(operator[0]),
                    subs.canonicalized_name(operator[1])];
        });
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
            var operand, i, index, m, related_regexp;
            for (i = 0; i < operators.length; i++) {
                operand = operators[i][1];
                switch (operators[i][0]) {
                case 'is':
                    if (operand === 'private') {
                        if (message.type !== 'private') {
                            return false;
                        }
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

                case 'near':
                    return true;

                case 'id':
                    return message.id.toString() === operand;

                case 'stream':
                    if (message.type !== 'stream') {
                        return false;
                    }

                    if (page_params.domain === "mit.edu") {
                        // MIT users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
                        // (unsocial, ununsocial, social.d, etc)
                        // TODO: hoist the regex compiling out of the closure
                        m = /^(?:un)*(.+?)(?:\.d)*$/i.exec(operand);
                        var base_stream_name = operand;
                        if (m !== null && m[1] !== undefined) {
                            base_stream_name = m[1];
                        }
                        related_regexp = new RegExp(/^(un)*/.source + util.escape_regexp(base_stream_name) + /(\.d)*$/.source, 'i');
                        if (! related_regexp.test(message.stream)) {
                            return false;
                        }
                    } else if (message.stream.toLowerCase() !== operand) {
                        return false;
                    }
                    break;

                case 'topic':
                    if (message.type !== 'stream') {
                        return false;
                    }

                    if (page_params.domain === "mit.edu") {
                        // MIT users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
                        // (foo, foo.d, foo.d.d, etc)
                        // TODO: hoist the regex compiling out of the closure
                        m = /^(.*?)(?:\.d)*$/i.exec(operand);
                        var base_topic = operand;
                        if (m !== null && m[1] !== undefined) {
                            base_topic = m[1];
                        }

                        // Additionally, MIT users expect the empty instance and
                        // instance "personal" to be the same.
                        if (base_topic === ''
                            || base_topic.toLowerCase() === 'personal'
                            || base_topic.toLowerCase() === '(instance "")')
                        {
                            related_regexp = /^(|personal|\(instance ""\))(\.d)*$/i;
                        } else {
                            related_regexp = new RegExp(/^/.source + util.escape_regexp(base_topic) + /(\.d)*$/.source, 'i');
                        }

                        if (! related_regexp.test(message.subject)) {
                            return false;
                        }
                    } else if (message.subject.toLowerCase() !== operand) {
                        return false;
                    }
                    break;

                case 'sender':
                    if ((message.sender_email.toLowerCase() !== operand)) {
                        return false;
                    }
                    break;

                case 'pm-with':
                    if ((message.type !== 'private') ||
                        message.reply_to.toLowerCase() !== operand.split(',').sort().join(',')) {
                        return false;
                    }
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

// A small concession to unit testing follows:
exports._set_current_filter = function (filter) {
    current_filter = filter;
};

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
        return [];
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
exports.unparse = function (operators) {
    var parts = _.map(operators, function (elem) {
        var operator = elem[0];
        if (operator === 'search') {
            // Search terms are the catch-all case.
            // All tokens that don't start with a known operator and
            // a colon are glued together to form a search term.
            return elem[1];
        } else {
            return elem[0] + ':' + encodeOperand(elem[1].toString().toLowerCase());
        }
    });
    return parts.join(' ');
};

exports.search_string = function () {
    return exports.unparse(exports.operators());
};

// Collect operators which appear only once into an object,
// and discard those which appear more than once.
function collect_single(operators) {
    var seen   = new Dict();
    var result = new Dict();
    _.each(operators, function (elem) {
        var key = elem[0];
        if (seen.has(key)) {
            result.del(key);
        } else {
            result.set(key, elem[1]);
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
exports.set_compose_defaults = function (opts) {
    var single = collect_single(exports.operators());

    // Set the stream, subject, and/or PM recipient if they are
    // uniquely specified in the narrow view.

    if (single.has('stream')) {
        opts.stream = single.get('stream');
    }

    if (single.has('topic')) {
        opts.subject = single.get('topic');
    }

    if (single.has('pm-with')) {
        opts.private_message_recipient = single.get('pm-with');
    }
};

// Parse a string into a list of operators (see below).
exports.parse = function (str) {
    var operators   = [];
    var search_term = [];
    var matches = str.match(/"[^"]+"|\S+/g);
    if (matches === null) {
        return operators;
    }
    _.each(matches, function (token) {
        var parts, operator;
        if (token.length === 0) {
            return;
        }
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
    if (search_term.length > 0) {
        operators.push(['search', search_term.join(' ')]);
    }
    return operators;
};

exports.message_in_home = function (message) {
    if (message.type === "private") {
        return true;
    }

    return subs.in_home_view(message.stream);
};

exports.stream = function () {
    if (current_filter === undefined) {
        return undefined;
    }
    var stream_operands = current_filter.operands("stream");
    if (stream_operands.length === 1) {
        return stream_operands[0];
    }
    return undefined;
};

exports.activate = function (operators, opts) {
    if (operators.length === 0) {
        return exports.deactivate();
    }
    var filter = new Filter(operators);

    opts = _.defaults({}, opts, {
        then_select_id: home_msg_list.selected_id(),
        select_first_unread: false,
        change_hash: true,
        trigger: 'unknown'
    });
    if (filter.has_operator("near")) {
        opts.then_select_id = filter.operands("near")[0];
        opts.select_first_unread = false;
    }
    if (filter.has_operator("id")) {
        opts.then_select_id = filter.operands("id")[0];
        opts.select_first_unread = false;
    }

    if (opts.then_select_id === -1) {
        // If we're loading the page via a narrowed URL, we may not
        // have setup the home view yet.  In that case, use the
        // initial pointer.  We can remove this code if we later move
        // to a model where home_msg_list.selected_id() is always
        // initialized early.
        opts.then_select_id = page_params.initial_pointer;
        opts.select_first_unread = false;
    }

    var was_narrowed_already = exports.active();
    var then_select_id = opts.then_select_id;
    var then_select_offset;
    if (!opts.select_first_unread && rows.get(then_select_id, current_msg_list.table_name).length > 0) {
        then_select_offset = rows.get(then_select_id, current_msg_list.table_name).offset().top -
            viewport.scrollTop();
    }

    if (!was_narrowed_already) {
        message_tour.start_tour(current_msg_list.selected_id());
    }

    current_filter = filter;

    // Save how far from the pointer the top of the message list was.
    if (current_msg_list.selected_id() !== -1) {
        current_msg_list.pre_narrow_offset = current_msg_list.selected_row().offset().top - viewport.scrollTop();
    }

    var can_summarize = feature_flags.summarize_read_while_narrowed
        && !current_filter.is_search() && !exports.narrowed_by_reply();
    narrowed_msg_list = new MessageList('zfilt', current_filter, {
        collapse_messages: ! current_filter.is_search(),
        summarize_read: can_summarize ? 'stream' : false
    });


    current_msg_list = narrowed_msg_list;

    function maybe_select_closest() {
        if (! narrowed_msg_list.empty()) {
            if (opts.select_first_unread) {
                then_select_id = narrowed_msg_list.last().id;
                var first_unread = _.find(narrowed_msg_list.all(),
                                          unread.message_unread);
                if (first_unread) {
                    then_select_id = first_unread.id;
                }
            }

            var preserve_pre_narrowing_screen_position =
                !opts.select_first_unread &&
                (narrowed_msg_list.get(then_select_id) !== undefined) &&
                (then_select_offset !== undefined);

            var then_scroll = !preserve_pre_narrowing_screen_position;

            narrowed_msg_list.select_id(then_select_id, {then_scroll: then_scroll,
                                                         use_closest: true
                                                        });

            if (preserve_pre_narrowing_screen_position) {
                // Scroll so that the selected message is in the same
                // position in the viewport as it was prior to
                // narrowing
                viewport.scrollTop(rows.get(then_select_id, narrowed_msg_list.table_name).offset().top
                                   - then_select_offset);
            }
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
        num_before: 50,
        num_after: 50,
        msg_list: narrowed_msg_list,
        cont: function (messages) {
            if (defer_selecting_closest) {
                maybe_select_closest();
            }
        },
        cont_will_add_messages: false
    });

    // Show the new set of messages.
    $("body").addClass("narrowed_view");
    $("#zfilt").addClass("focused_table");
    $("#zhome").removeClass("focused_table");

    // Deal with message condensing/uncondensing.
    // In principle, this code causes us to scroll around because divs
    // above us could change size -- which is problematic, because it
    // could cause us to lose our position. But doing this here, right
    // after showing the table, seems to cause us to win the race.
    _.each($("tr.message_row"), ui.process_condensing);

    reset_load_more_status();
    if (! defer_selecting_closest) {
        maybe_select_closest();
    }

    // Put the narrow operators in the URL fragment.
    // Disabled when the URL fragment was the source
    // of this narrow.
    if (opts.change_hash) {
        hashchange.save_narrow(operators);
    }

    // Put the narrow operators in the search bar.
    $('#search_query').val(exports.unparse(operators));
    search.update_button_visibility();
    compose.update_recipient_on_narrow();
    compose_fade.update_message_list();

    $(document).trigger($.Event('narrow_activated.zulip', {msg_list: narrowed_msg_list,
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
    mark_message_as_read(original);
    opts = _.defaults({}, opts, {then_select_id: target_id});
    exports.activate([
            ['stream',  original.stream],
            ['topic', original.subject]
        ], opts);
};

// Called for the 'narrow by stream' hotkey.
exports.by_recipient = function (target_id, opts) {
    opts = _.defaults({}, opts, {then_select_id: target_id});
    var message = current_msg_list.get(target_id);
    mark_message_as_read(message);
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
    opts = _.defaults({}, opts, {then_select_id: target_id});
    narrow.activate([["near", target_id]], opts);
};

exports.deactivate = function () {
    if (current_filter === undefined) {
        return;
    }

    if (ui.actively_scrolling()) {
        // There is no way to intercept in-flight scroll events, and they will
        // cause you to end up in the wrong place if you are actively scrolling
        // on an unnarrow. Wait a bit and try again once the scrolling is over.
        setTimeout(exports.deactivate, 50);
        return;
    }

    current_filter = undefined;

    exports.hide_empty_narrow_message();

    $("body").removeClass('narrowed_view');
    $("#zfilt").removeClass('focused_table');
    $("#zhome").addClass('focused_table');

    $('#search_query').val('');
    reset_load_more_status();

    var visited_messages = message_tour.get_tour();
    home_msg_list.advance_past_messages(visited_messages);
    message_tour.finish_tour();

    current_msg_list = home_msg_list;
    var preserve_pre_narrowing_screen_position =
        (current_msg_list.selected_row().length > 0) &&
        (current_msg_list.pre_narrow_offset !== undefined);

    if (feature_flags.summarize_read_while_narrowed) {
        // TODO: avoid a full re-render
        // Necessary to replace messages read in the narrow with summary blocks
        current_msg_list.rerender();
    }

    // We fall back to the closest selected id, if the user has removed a stream from the home
    // view since leaving it the old selected id might no longer be there
    current_msg_list.select_id(current_msg_list.selected_id(), {
        then_scroll: !preserve_pre_narrowing_screen_position,
        use_closest: true
    });

    if (preserve_pre_narrowing_screen_position) {
        // We scroll the user back to exactly the offset from the selected
        // message that he was at the time that he narrowed.
        // TODO: Make this correctly handle the case of resizing while narrowed.
        viewport.scrollTop(current_msg_list.selected_row().offset().top - current_msg_list.pre_narrow_offset);
    }

    hashchange.save_narrow();
    compose_fade.update_message_list();

    $(document).trigger($.Event('narrow_deactivated.zulip', {msg_list: current_msg_list}));
};

exports.restore_home_state = function () {
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
        } else if (first_operand === "private") {
            // You have no private messages.
            return $("#empty_narrow_all_private_message");
        }
    } else if ((first_operator === "stream") && !subs.is_subscribed(first_operand)) {
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

// Are we narrowed to PMs: all PMs or PMs with particular people.
exports.narrowed_to_pms = function () {
    if (current_filter === undefined) {
        return false;
    }
    return (current_filter.has_operator("pm-with") ||
            current_filter.has_operand("is", "private"));
};

// We auto-reply under certain conditions, namely when you're narrowed
// to a PM (or huddle), and when you're narrowed to some stream/subject pair
exports.narrowed_by_reply = function () {
    if (current_filter === undefined) {
        return false;
    }
    var operators = current_filter.operators();
    return ((operators.length === 1 &&
             current_filter.operands("pm-with").length === 1) ||
            (operators.length === 2 &&
             current_filter.operands("stream").length === 1 &&
             current_filter.operands("topic").length === 1));
};

exports.narrowed_to_search = function () {
    return (current_filter !== undefined) && current_filter.is_search();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = narrow;
}
