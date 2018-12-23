var Filter = (function () {

function zephyr_stream_name_match(message, operand) {
    // Zephyr users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
    // (unsocial, ununsocial, social.d, etc)
    // TODO: hoist the regex compiling out of the closure
    var m = /^(?:un)*(.+?)(?:\.d)*$/i.exec(operand);
    var base_stream_name = operand;
    if (m !== null && m[1] !== undefined) {
        base_stream_name = m[1];
    }
    var related_regexp = new RegExp(/^(un)*/.source + util.escape_regexp(base_stream_name) + /(\.d)*$/.source, 'i');
    return related_regexp.test(message.stream);
}

function zephyr_topic_name_match(message, operand) {
    // Zephyr users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
    // (foo, foo.d, foo.d.d, etc)
    // TODO: hoist the regex compiling out of the closure
    var m = /^(.*?)(?:\.d)*$/i.exec(operand);
    var base_topic = m[1];
    var related_regexp;

    // Additionally, Zephyr users expect the empty instance and
    // instance "personal" to be the same.
    if (base_topic === ''
        || base_topic.toLowerCase() === 'personal'
        || base_topic.toLowerCase() === '(instance "")') {
        related_regexp = /^(|personal|\(instance ""\))(\.d)*$/i;
    } else {
        related_regexp = new RegExp(/^/.source + util.escape_regexp(base_topic) + /(\.d)*$/.source, 'i');
    }

    return related_regexp.test(util.get_message_topic(message));
}

function message_in_home(message) {
    if (message.type === "private" || message.mentioned ||
        page_params.narrow_stream !== undefined &&
         message.stream.toLowerCase() === page_params.narrow_stream.toLowerCase()) {
        return true;
    }

    return stream_data.in_home_view(message.stream_id);
}

function message_matches_search_term(message, operator, operand) {
    switch (operator) {
    case 'is':
        if (operand === 'private') {
            return message.type === 'private';
        } else if (operand === 'starred') {
            return message.starred;
        } else if (operand === 'mentioned') {
            return message.mentioned;
        } else if (operand === 'alerted') {
            return message.alerted;
        } else if (operand === 'unread') {
            return unread.message_unread(message);
        }
        return true; // is:whatever returns true

    case 'in':
        if (operand === 'home') {
            return message_in_home(message);
        } else if (operand === 'all') {
            return true;
        }
        return true; // in:whatever returns true

    case 'near':
        // this is all handled server side
        return true;

    case 'id':
        return message.id.toString() === operand;

    case 'stream':
        if (message.type !== 'stream') {
            return false;
        }

        operand = operand.toLowerCase();
        if (page_params.realm_is_zephyr_mirror_realm) {
            return zephyr_stream_name_match(message, operand);
        }

        // Try to match by stream_id if have a valid sub for
        // the operand.
        var stream_id = stream_data.get_stream_id(operand);
        if (stream_id) {
            return message.stream_id === stream_id;
        }

        // We need this fallback logic in case we have a message
        // loaded for a stream that we are no longer
        // subscribed to (or that was deleted).
        return message.stream.toLowerCase() === operand;

    case 'topic':
        if (message.type !== 'stream') {
            return false;
        }

        operand = operand.toLowerCase();
        if (page_params.realm_is_zephyr_mirror_realm) {
            return zephyr_topic_name_match(message, operand);
        }
        return util.get_message_topic(message).toLowerCase() === operand;


    case 'sender':
        return people.id_matches_email_operand(message.sender_id, operand);

    case 'group-pm-with':
        var operand_ids = people.pm_with_operand_ids(operand);
        if (!operand_ids) {
            return false;
        }
        var user_ids = people.group_pm_with_user_ids(message);
        if (!user_ids) {
            return false;
        }
        return user_ids.indexOf(operand_ids[0]) !== -1;
        // We should also check if the current user is in the recipient list (user_ids) of the
        // message, but it is implicit by the fact that the current user has access to the message.

    case 'pm-with':
        // TODO: use user_ids, not emails here
        if (message.type !== 'private') {
            return false;
        }
        operand_ids = people.pm_with_operand_ids(operand);
        if (!operand_ids) {
            return false;
        }
        user_ids = people.pm_with_user_ids(message);
        if (!user_ids) {
            return false;
        }

        return _.isEqual(operand_ids, user_ids);
    }

    return true; // unknown operators return true (effectively ignored)
}


function Filter(operators) {
    if (operators === undefined) {
        this._operators = [];
    } else {
        this._operators = this._canonicalize_operators(operators);
    }
}

Filter.canonicalize_operator = function (operator) {
    operator = operator.toLowerCase();

    if (operator === 'from') {
        return 'sender';
    }

    if (util.is_topic_synonym(operator)) {
        return 'topic';
    }
    return operator;
};

Filter.canonicalize_term = function (opts) {
    var negated = opts.negated;
    var operator = opts.operator;
    var operand = opts.operand;

    // Make negated be explicitly false for both clarity and
    // simplifying deepEqual checks in the tests.
    if (!negated) {
        negated = false;
    }

    operator = Filter.canonicalize_operator(operator);

    switch (operator) {
    case 'has':
        // images -> image, etc.
        operand = operand.replace(/s$/, '');
        break;

    case 'stream':
        operand = stream_data.get_name(operand);
        break;
    case 'topic':
        break;
    case 'sender':
    case 'pm-with':
        operand = operand.toString().toLowerCase();
        if (operand === 'me') {
            operand = people.my_current_email();
        }
        break;
    case 'group-pm-with':
        operand = operand.toString().toLowerCase();
        break;
    case 'search':
        // The mac app automatically substitutes regular quotes with curly
        // quotes when typing in the search bar.  Curly quotes don't trigger our
        // phrase search behavior, however.  So, we replace all instances of
        // curly quotes with regular quotes when doing a search.  This is
        // unlikely to cause any problems and is probably what the user wants.
        operand = operand.toString().toLowerCase().replace(/[\u201c\u201d]/g, '"');
        break;
    default:
        operand = operand.toString().toLowerCase();
    }

    // We may want to consider allowing mixed-case operators at some point
    return {
        negated: negated,
        operator: operator,
        operand: operand,
    };
};

/* We use a variant of URI encoding which looks reasonably
   nice and still handles unambiguously cases such as
   spaces in operands.

   This is just for the search bar, not for saving the
   narrow in the URL fragment.  There we do use full
   URI encoding to avoid problematic characters. */
function encodeOperand(operand) {
    return operand.replace(/%/g, '%25')
        .replace(/\+/g, '%2B')
        .replace(/ /g, '+')
        .replace(/"/g, '%22');
}

function decodeOperand(encoded, operator) {
    encoded = encoded.replace(/"/g, '');
    if (_.contains(['group-pm-with', 'pm-with', 'sender', 'from'], operator) === false) {
        encoded = encoded.replace(/\+/g, ' ');
    }
    return util.robust_uri_decode(encoded).trim();
}

// Parse a string into a list of operators (see below).
Filter.parse = function (str) {
    var operators   = [];
    var search_term = [];
    var negated;
    var operator;
    var operand;
    var term;

    // Match all operands that either have no spaces, or are surrounded by
    // quotes, preceded by an optional operator that may have a space after it.
    var matches = str.match(/([^\s:]+: ?)?("[^"]+"?|\S+)/g);
    if (matches === null) {
        return operators;
    }
    _.each(matches, function (token) {
        var parts;
        var operator;
        parts = token.split(':');
        if (token[0] === '"' || parts.length === 1) {
            // Looks like a normal search term.
            search_term.push(token);
        } else {
            // Looks like an operator.
            negated = false;
            operator = parts.shift();
            if (operator[0] === '-') {
                negated = true;
                operator = operator.slice(1);
            }
            operand = decodeOperand(parts.join(':'), operator);

            // We use Filter.operator_to_prefix() checks if the
            // operator is known.  If it is not known, then we treat
            // it as a search for the given string (which may contain
            // a `:`), not as a search operator.
            if (Filter.operator_to_prefix(operator, negated) === '') {
                // Put it as a search term, to not have duplicate operators
                search_term.push(token);
                return;
            }
            term = {negated: negated, operator: operator, operand: operand};
            operators.push(term);
        }
    });
    // NB: Callers of 'parse' can assume that the 'search' operator is last.
    if (search_term.length > 0) {
        operator = 'search';
        operand = search_term.join(' ');
        term = {operator: operator, operand: operand, negated: false};
        operators.push(term);
    }
    return operators;
};

/* Convert a list of operators to a string.
   Each operator is a key-value pair like

       ['topic', 'my amazing topic']

   These are not keys in a JavaScript object, because we
   might need to support multiple operators of the same type.
*/
Filter.unparse = function (operators) {
    var parts = _.map(operators, function (elem) {

        if (elem.operator === 'search') {
            // Search terms are the catch-all case.
            // All tokens that don't start with a known operator and
            // a colon are glued together to form a search term.
            return elem.operand;
        }
        var sign = elem.negated ? '-' : '';
        if (elem.operator === '') {
            return elem.operand;
        }
        return sign + elem.operator + ':' + encodeOperand(elem.operand.toString());
    });
    return parts.join(' ');
};



Filter.prototype = {
    predicate: function () {
        if (this._predicate === undefined) {
            this._predicate = this._build_predicate();
        }
        return this._predicate;
    },

    operators: function () {
        return this._operators;
    },

    public_operators: function () {
        var safe_to_return = _.filter(this._operators, function (value) {
            // Filter out the embedded narrow (if any).
            return !(page_params.narrow_stream !== undefined &&
                     value.operator === "stream" &&
                     value.operand.toLowerCase() === page_params.narrow_stream.toLowerCase());
        });
        return safe_to_return;
    },

    operands: function (operator) {
        return _.chain(this._operators)
            .filter(function (elem) { return !elem.negated && elem.operator === operator; })
            .map(function (elem) { return elem.operand; })
            .value();
    },

    has_operand: function (operator, operand) {
        return _.any(this._operators, function (elem) {
            return !elem.negated && (elem.operator === operator && elem.operand === operand);
        });
    },

    has_operator: function (operator) {
        return _.any(this._operators, function (elem) {
            if (elem.negated && !_.contains(['search', 'has'], elem.operator)) {
                return false;
            }
            return elem.operator === operator;
        });
    },

    is_search: function () {
        return this.has_operator('search');
    },

    can_apply_locally: function () {
        if (this.is_search()) {
            // The semantics for matching keywords are implemented
            // by database plugins, and we don't have JS code for
            // that, plus search queries tend to go too far back in
            // history.
            return false;
        }

        if (this.has_operator('has')) {
            // See #6186 to see why we currently punt on 'has:foo'
            // queries.  This can be fixed, there are just some random
            // complications that make it non-trivial.
            return false;
        }

        // If we get this far, we're good!
        return true;
    },

    _canonicalize_operators: function (operators_mixed_case) {
        return _.map(operators_mixed_case, function (tuple) {
            return Filter.canonicalize_term(tuple);
        });
    },

    filter_with_new_topic: function (new_topic) {
        var terms = _.map(this._operators, function (term) {
            var new_term = _.clone(term);
            if (new_term.operator === 'topic' && !new_term.negated) {
                new_term.operand = new_topic;
            }
            return new_term;
        });
        return new Filter(terms);
    },

    has_topic: function (stream_name, topic) {
        return this.has_operand('stream', stream_name) && this.has_operand('topic', topic);
    },

    sorted_term_types: function () {
        var terms = this._operators;
        var term_types = _.map(terms, Filter.term_type);
        var sorted_terms = Filter.sorted_term_types(term_types);
        return sorted_terms;
    },

    is_exactly: function () {
        // TODO: in ES6 use spread operator
        //
        // Examples calls:
        //     filter.is_exactly('stream', 'topic')
        //     filter.is_exactly('pm-with')
        var wanted_term_types = [].slice.call(arguments);
        var term_types = this.sorted_term_types();

        return _.isEqual(term_types, wanted_term_types);
    },

    is_reading_mode: function () {
        // We only turn on "reading mode" for filters that
        // have contiguous messages for a narrow, as opposed
        // to "random access" queries like search:<keyword>
        // or id:<number> that jump you to parts of the message
        // view where you might only care about reading the
        // current message.
        var term_types = this.sorted_term_types();
        var wanted_list = [
            ['stream'],
            ['stream', 'topic'],
            ['is-private'],
            ['pm-with'],
        ];
        return _.any(wanted_list, function (wanted_types) {
            return _.isEqual(wanted_types, term_types);
        });
    },

    can_bucket_by: function () {
        // TODO: in ES6 use spread operator
        //
        // Examples call:
        //     filter.can_bucket_by('stream', 'topic')
        //
        // The use case of this function is that we want
        // to know if a filter can start with a bucketing
        // data structure similar to the ones we have in
        // unread.js to pre-filter ids, rather than apply
        // a predicate to a larger list of candidate ids.
        //
        // (It's for optimization, basically.)
        var wanted_term_types = [].slice.call(arguments);
        var all_term_types = this.sorted_term_types();
        var term_types = all_term_types.slice(0, wanted_term_types.length);

        return _.isEqual(term_types, wanted_term_types);
    },

    first_valid_id_from: function (msg_ids) {
        var predicate = this.predicate();

        var first_id = _.find(msg_ids, function (msg_id) {
            var message = message_store.get(msg_id);

            if (message === undefined) {
                return false;
            }

            return predicate(message);
        });

        return first_id;
    },

    update_email: function (user_id, new_email) {
        _.each(this._operators, function (term) {
            switch (term.operator) {
            case 'group-pm-with':
            case 'pm-with':
            case 'sender':
            case 'from':
                term.operand = people.update_email_in_reply_to(
                    term.operand,
                    user_id,
                    new_email
                );
            }
        });
    },

    // Build a filter function from a list of operators.
    _build_predicate: function () {
        var operators = this._operators;

        if (!this.can_apply_locally()) {
            return function () { return true; };
        }

        // FIXME: This is probably pretty slow.
        // We could turn it into something more like a compiler:
        // build JavaScript code in a string and then eval() it.

        return function (message) {
            return _.all(operators, function (term) {
                var ok = message_matches_search_term(message, term.operator, term.operand);
                if (term.negated) {
                    ok = !ok;
                }
                return ok;
            });
        };
    },
};

Filter.term_type = function (term) {
    var operator = term.operator;
    var operand = term.operand;
    var negated = term.negated;

    var result = negated ? 'not-' : '';

    result += operator;

    if (_.contains(['is', 'has'], operator)) {
        result += '-' + operand;
    }

    return result;
};

Filter.sorted_term_types = function (term_types) {
    var levels = [
        'stream', 'topic',
        'pm-with', 'group-pm-with', 'sender',
        'near', 'id',
        'is-alerted', 'is-mentioned', 'is-private',
        'is-starred', 'is-unread',
        'has-link', 'has-image', 'has-attachment',
        'search',
    ];

    function level(term_type) {
        var i = levels.indexOf(term_type);
        if (i === -1) {
            i = 999;
        }
        return i;
    }

    function compare(a, b) {
        var diff = level(a) - level(b);
        if (diff !== 0) {
            return diff;
        }
        return util.strcmp(a, b);
    }

    return _.clone(term_types).sort(compare);
};

Filter.operator_to_prefix = function (operator, negated) {
    var verb;

    operator = Filter.canonicalize_operator(operator);

    if (operator === 'search') {
        return negated ? 'exclude' : 'search for';
    }

    verb = negated ? 'exclude ' : '';

    switch (operator) {
    case 'stream':
        return verb + 'stream';

    case 'near':
        return verb + 'messages around';

    // Note: We hack around using this in "describe" below.
    case 'has':
        return verb + 'messages with one or more';

    case 'id':
        return verb + 'message ID';

    case 'topic':
        return verb + 'topic';

    case 'sender':
        return verb + 'sent by';

    case 'pm-with':
        return verb + 'private messages with';

    case 'in':
        return verb + 'messages in';

    // Note: We hack around using this in "describe" below.
    case 'is':
        return verb + 'messages that are';

    case 'group-pm-with':
        return verb + 'group private messages including';
    }
    return '';
};

function describe_is_operator(operator) {
    var verb = operator.negated ? 'exclude ' : '';
    var operand = operator.operand;
    var operand_list = ['private', 'starred', 'alerted', 'unread'];
    if (operand_list.indexOf(operand) !== -1) {
        return verb + operand + ' messages';
    } else if (operand === 'mentioned') {
        return verb + '@-mentions';
    }
    return 'invalid ' + operand + ' operand for is operator';
}

// Convert a list of operators to a human-readable description.
function describe_unescaped(operators) {
    if (operators.length === 0) {
        return 'all messages';
    }

    var parts = [];

    if (operators.length >= 2) {
        var is = function (term, expected) {
            return term.operator === expected && !term.negated;
        };

        if (is(operators[0], 'stream') && is(operators[1], 'topic')) {
            var stream = operators[0].operand;
            var topic = operators[1].operand;
            var part = "stream " + stream + ' > ' + topic;
            parts = [part];
            operators = operators.slice(2);
        }
    }

    var more_parts = _.map(operators, function (elem) {
        var operand = elem.operand;
        var canonicalized_operator = Filter.canonicalize_operator(elem.operator);
        if (canonicalized_operator === 'is') {
            return describe_is_operator(elem);
        }
        if (canonicalized_operator === 'has') {
            // search_suggestion.get_suggestions takes care that this message will
            // only be shown if the `has` operator is not at the last.
            var valid_has_operands = ['image', 'images', 'link', 'links', 'attachment', 'attachments'];
            if (valid_has_operands.indexOf(operand) === -1) {
                return 'invalid ' + operand + ' operand for has operator';
            }
        }
        var prefix_for_operator = Filter.operator_to_prefix(canonicalized_operator,
                                                            elem.negated);
        if (prefix_for_operator !== '') {
            return prefix_for_operator + ' ' + operand;
        }
        return "unknown operator";
    });
    return parts.concat(more_parts).join(', ');
}

Filter.describe = function (operators) {
    return Handlebars.Utils.escapeExpression(describe_unescaped(operators));
};

return Filter;

}());
if (typeof module !== 'undefined') {
    module.exports = Filter;
}

window.Filter = Filter;
