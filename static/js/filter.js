function zephyr_stream_name_match(message, operand) {
    // Zephyr users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
    // (unsocial, ununsocial, social.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(?:un)*(.+?)(?:\.d)*$/i.exec(operand);
    let base_stream_name = operand;
    if (m !== null && m[1] !== undefined) {
        base_stream_name = m[1];
    }
    const related_regexp = new RegExp(/^(un)*/.source + util.escape_regexp(base_stream_name) + /(\.d)*$/.source, 'i');
    return related_regexp.test(message.stream);
}

function zephyr_topic_name_match(message, operand) {
    // Zephyr users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
    // (foo, foo.d, foo.d.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(.*?)(?:\.d)*$/i.exec(operand);
    const base_topic = m[1];
    let related_regexp;

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

    // We don't display muted streams in 'All messages' view
    return !stream_data.is_muted(message.stream_id);
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

    case 'stream': {
        if (message.type !== 'stream') {
            return false;
        }

        operand = operand.toLowerCase();
        if (page_params.realm_is_zephyr_mirror_realm) {
            return zephyr_stream_name_match(message, operand);
        }

        // Try to match by stream_id if have a valid sub for
        // the operand.
        const stream_id = stream_data.get_stream_id(operand);
        if (stream_id) {
            return message.stream_id === stream_id;
        }

        // We need this fallback logic in case we have a message
        // loaded for a stream that we are no longer
        // subscribed to (or that was deleted).
        return message.stream.toLowerCase() === operand;
    }

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

    case 'group-pm-with': {
        const operand_ids = people.pm_with_operand_ids(operand);
        if (!operand_ids) {
            return false;
        }
        const user_ids = people.group_pm_with_user_ids(message);
        if (!user_ids) {
            return false;
        }
        return user_ids.includes(operand_ids[0]);
        // We should also check if the current user is in the recipient list (user_ids) of the
        // message, but it is implicit by the fact that the current user has access to the message.
    }

    case 'pm-with': {
        // TODO: use user_ids, not emails here
        if (message.type !== 'private') {
            return false;
        }
        const operand_ids = people.pm_with_operand_ids(operand);
        if (!operand_ids) {
            return false;
        }
        const user_ids = people.pm_with_user_ids(message);
        if (!user_ids) {
            return false;
        }

        return _.isEqual(operand_ids, user_ids);
    }
    }

    return true; // unknown operators return true (effectively ignored)
}


function Filter(operators) {
    if (operators === undefined) {
        this._operators = [];
    } else {
        this._operators = this.fix_operators(operators);
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
    let negated = opts.negated;
    let operator = opts.operator;
    let operand = opts.operand;

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
    if (['group-pm-with', 'pm-with', 'sender', 'from'].includes(operator) === false) {
        encoded = encoded.replace(/\+/g, ' ');
    }
    return util.robust_uri_decode(encoded).trim();
}

// Parse a string into a list of operators (see below).
Filter.parse = function (str) {
    const operators   = [];
    const search_term = [];
    let negated;
    let operator;
    let operand;
    let term;

    // Match all operands that either have no spaces, or are surrounded by
    // quotes, preceded by an optional operator that may have a space after it.
    const matches = str.match(/([^\s:]+: ?)?("[^"]+"?|\S+)/g);
    if (matches === null) {
        return operators;
    }

    for (const token of matches) {
        let operator;
        const parts = token.split(':');
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
                continue;
            }
            term = {negated: negated, operator: operator, operand: operand};
            operators.push(term);
        }
    }

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
    const parts = operators.map(elem => {

        if (elem.operator === 'search') {
            // Search terms are the catch-all case.
            // All tokens that don't start with a known operator and
            // a colon are glued together to form a search term.
            return elem.operand;
        }
        const sign = elem.negated ? '-' : '';
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
        const safe_to_return = this._operators.filter(
            // Filter out the embedded narrow (if any).
            value =>
                !(
                    page_params.narrow_stream !== undefined &&
                    value.operator === "stream" &&
                    value.operand.toLowerCase() === page_params.narrow_stream.toLowerCase()
                )
        );
        return safe_to_return;
    },

    operands: function (operator) {
        return _.chain(this._operators)
            .filter(function (elem) { return !elem.negated && elem.operator === operator; })
            .map(function (elem) { return elem.operand; })
            .value();
    },

    has_negated_operand: function (operator, operand) {
        return this._operators.some(
            elem => elem.negated && (elem.operator === operator && elem.operand === operand)
        );
    },

    has_operand: function (operator, operand) {
        return this._operators.some(
            elem => !elem.negated && (elem.operator === operator && elem.operand === operand)
        );
    },

    has_operator: function (operator) {
        return this._operators.some(elem => {
            if (elem.negated && !['search', 'has'].includes(elem.operator)) {
                return false;
            }
            return elem.operator === operator;
        });
    },

    is_search: function () {
        return this.has_operator('search');
    },

    can_mark_messages_read: function () {
        const term_types = this.sorted_term_types();

        if (_.isEqual(term_types, ['stream', 'topic'])) {
            return true;
        }

        if (_.isEqual(term_types, ['pm-with'])) {
            return true;
        }

        // TODO: Some users really hate it when Zulip marks messages as read
        // in interleaved views, so we will eventually have a setting
        // that early-exits before the subsequent checks.

        if (_.isEqual(term_types, ['stream'])) {
            return true;
        }

        if (_.isEqual(term_types, ['is-private'])) {
            return true;
        }

        if (_.isEqual(term_types, ['is-mentioned'])) {
            return true;
        }

        if (_.isEqual(term_types, [])) {
            // All view
            return true;
        }

        if (term_types.length === 1 && ['in-home', 'in-all'].includes(term_types[0])) {
            return true;
        }

        return false;
    },

    allow_use_first_unread_when_narrowing: function () {
        return this.can_mark_messages_read() || this.has_operator('is');
    },

    contains_only_private_messages: function () {
        return this.has_operator("is") && this.operands("is")[0] === "private" ||
            this.has_operator("pm-with") || this.has_operator("group-pm-with");
    },

    includes_full_stream_history: function () {
        return this.has_operator("stream") || this.has_operator("streams");
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

        if (this.has_operator('streams') ||
            this.has_negated_operand('streams', 'public')) {
            return false;
        }

        // If we get this far, we're good!
        return true;
    },

    fix_operators: function (operators) {
        operators = this._canonicalize_operators(operators);
        operators = this._fix_redundant_is_private(operators);
        return operators;
    },

    _fix_redundant_is_private: function (terms) {
        const is_pm_with = (term) => {
            return Filter.term_type(term) === 'pm-with';
        };

        if (!terms.some(is_pm_with)) {
            return terms;
        }

        return terms.filter(term => Filter.term_type(term) !== 'is-private');
    },

    _canonicalize_operators: function (operators_mixed_case) {
        return operators_mixed_case.map(tuple => Filter.canonicalize_term(tuple));
    },

    filter_with_new_topic: function (new_topic) {
        const terms = this._operators.map(term => {
            const new_term = _.clone(term);
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
        const terms = this._operators;
        const term_types = terms.map(Filter.term_type);
        const sorted_terms = Filter.sorted_term_types(term_types);
        return sorted_terms;
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
        const wanted_term_types = [].slice.call(arguments);
        const all_term_types = this.sorted_term_types();
        const term_types = all_term_types.slice(0, wanted_term_types.length);

        return _.isEqual(term_types, wanted_term_types);
    },

    first_valid_id_from: function (msg_ids) {
        const predicate = this.predicate();

        const first_id = _.find(msg_ids, function (msg_id) {
            const message = message_store.get(msg_id);

            if (message === undefined) {
                return false;
            }

            return predicate(message);
        });

        return first_id;
    },

    update_email: function (user_id, new_email) {
        for (const term of this._operators) {
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
        }
    },

    // Build a filter function from a list of operators.
    _build_predicate: function () {
        const operators = this._operators;

        if (!this.can_apply_locally()) {
            return function () { return true; };
        }

        // FIXME: This is probably pretty slow.
        // We could turn it into something more like a compiler:
        // build JavaScript code in a string and then eval() it.

        return function (message) {
            return _.all(operators, function (term) {
                let ok = message_matches_search_term(message, term.operator, term.operand);
                if (term.negated) {
                    ok = !ok;
                }
                return ok;
            });
        };
    },
};

Filter.term_type = function (term) {
    const operator = term.operator;
    const operand = term.operand;
    const negated = term.negated;

    let result = negated ? 'not-' : '';

    result += operator;

    if (['is', 'has', 'in', 'streams'].includes(operator)) {
        result += '-' + operand;
    }

    return result;
};

Filter.sorted_term_types = function (term_types) {
    const levels = [
        'in',
        'streams',
        'stream', 'topic',
        'pm-with', 'group-pm-with', 'sender',
        'near', 'id',
        'is-alerted', 'is-mentioned', 'is-private',
        'is-starred', 'is-unread',
        'has-link', 'has-image', 'has-attachment',
        'search',
    ];

    function level(term_type) {
        let i = levels.indexOf(term_type);
        if (i === -1) {
            i = 999;
        }
        return i;
    }

    function compare(a, b) {
        const diff = level(a) - level(b);
        if (diff !== 0) {
            return diff;
        }
        return util.strcmp(a, b);
    }

    return _.clone(term_types).sort(compare);
};

Filter.operator_to_prefix = function (operator, negated) {
    operator = Filter.canonicalize_operator(operator);

    if (operator === 'search') {
        return negated ? 'exclude' : 'search for';
    }

    const verb = negated ? 'exclude ' : '';

    switch (operator) {
    case 'stream':
        return verb + 'stream';
    case 'streams':
        return verb + 'streams';
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
    const verb = operator.negated ? 'exclude ' : '';
    const operand = operator.operand;
    const operand_list = ['private', 'starred', 'alerted', 'unread'];
    if (operand_list.includes(operand)) {
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

    let parts = [];

    if (operators.length >= 2) {
        const is = function (term, expected) {
            return term.operator === expected && !term.negated;
        };

        if (is(operators[0], 'stream') && is(operators[1], 'topic')) {
            const stream = operators[0].operand;
            const topic = operators[1].operand;
            const part = "stream " + stream + ' > ' + topic;
            parts = [part];
            operators = operators.slice(2);
        }
    }

    const more_parts = operators.map(elem => {
        const operand = elem.operand;
        const canonicalized_operator = Filter.canonicalize_operator(elem.operator);
        if (canonicalized_operator === 'is') {
            return describe_is_operator(elem);
        }
        if (canonicalized_operator === 'has') {
            // search_suggestion.get_suggestions takes care that this message will
            // only be shown if the `has` operator is not at the last.
            const valid_has_operands = ['image', 'images', 'link', 'links', 'attachment', 'attachments'];
            if (!valid_has_operands.includes(operand)) {
                return 'invalid ' + operand + ' operand for has operator';
            }
        }
        const prefix_for_operator = Filter.operator_to_prefix(canonicalized_operator,
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

module.exports = Filter;

window.Filter = Filter;
