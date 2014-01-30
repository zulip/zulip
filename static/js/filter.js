var Filter = (function () {

function filter_term(operator, operand) {
    // For legacy reasons we must represent filter_terms as tuples
    // until we phase out all the code that assumes tuples.
    var term = [];
    term[0] = operator;
    term[1] = operand;

    // This is the new style we are phasing in.  (Yes, the same
    // object can be treated like either a tuple or a struct.)
    term.operator = operator;
    term.operand = operand;

    return term;
}

function mit_edu_stream_name_match(message, operand) {
    // MIT users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
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

function mit_edu_topic_name_match(message, operand) {
    // MIT users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
    // (foo, foo.d, foo.d.d, etc)
    // TODO: hoist the regex compiling out of the closure
    var m = /^(.*?)(?:\.d)*$/i.exec(operand);
    var base_topic = m[1];
    var related_regexp;

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

    return related_regexp.test(message.subject);
}

function message_in_home(message) {
    if (message.type === "private" || message.mentioned ||
        (page_params.narrow_stream !== undefined &&
         message.stream.toLowerCase() === page_params.narrow_stream.toLowerCase())) {
        return true;
    }

    return stream_data.in_home_view(message.stream);
}

function message_matches_search_term(message, operator, operand) {
    switch (operator) {
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
        } else if (operand === 'alerted') {
            if (!message.alerted) {
                return false;
            }
        }

        break;

    case 'in':
        if (operand === 'home') {
            return message_in_home(message);
        }
        else if (operand === 'all') {
            break;
        }
        break;

    case 'near':
        break;

    case 'id':
        if (message.id.toString() !== operand) {
            return false;
        }
        break;

    case 'stream':
        if (message.type !== 'stream') {
            return false;
        }

        operand = operand.toLowerCase();
        if (page_params.domain === "mit.edu") {
            if (!mit_edu_stream_name_match(message, operand)) {
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

        operand = operand.toLowerCase();
        if (page_params.domain === "mit.edu") {
            if (!mit_edu_topic_name_match(message, operand)) {
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

    return true;
}


function Filter(operators) {
    if (operators === undefined) {
        this._operators = [];
    } else {
        this._operators = this._canonicalize_operators(operators);
    }
}

var canonical_operators = {"from": "sender", "subject": "topic"};

Filter.canonicalize_operator = function (operator) {
    operator = operator.toLowerCase();
    if (canonical_operators.hasOwnProperty(operator)) {
        return canonical_operators[operator];
    } else {
        return operator;
    }
};

Filter.canonicalize_tuple = function (tuple) {
    var operator = tuple[0];
    var operand = tuple[1];

    operator = Filter.canonicalize_operator(operator);

    switch (operator) {
    case 'stream':
        operand = stream_data.get_name(operand);
        break;
    case 'topic':
        break;
    case 'sender':
    case 'pm-with':
        operand = operand.toString().toLowerCase();
        if (operand === 'me') {
            operand = page_params.email;
        }
        break;
    default:
        operand = operand.toString().toLowerCase();
    }

    // We may want to consider allowing mixed-case operators at some point
    return filter_term(operator, operand);
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

function decodeOperand(encoded, operator) {
    if (operator !== 'pm-with' && operator !== 'sender') {
        encoded = encoded.replace(/\+/g, ' ');
    }
    return util.robust_uri_decode(encoded);
}

// Parse a string into a list of operators (see below).
Filter.parse = function (str) {
    var operators   = [];
    var search_term = [];
    var operand;

    var matches = str.match(/"[^"]+"|\S+/g);
    if (matches === null) {
        return operators;
    }
    _.each(matches, function (token) {
        var parts, operator;
        parts = token.split(':');
        if (token[0] === '"' || parts.length === 1) {
            // Looks like a normal search term.
            search_term.push(token);
        } else {
            // Looks like an operator.
            // FIXME: Should we skip unknown operator names here?
            operator = parts.shift();
            operand = decodeOperand(parts.join(':'), operator);
            operators.push(filter_term(operator, operand));
        }
    });
    // NB: Callers of 'parse' can assume that the 'search' operator is last.
    if (search_term.length > 0) {
        operand = search_term.join(' ');
        operators.push(filter_term('search', operand));
    }
    return operators;
};

/* Convert a list of operators to a string.
   Each operator is a key-value pair like

       ['subject', 'my amazing subject']

   These are not keys in a JavaScript object, because we
   might need to support multiple operators of the same type.
*/
Filter.unparse = function (operators) {
    var parts = _.map(operators, function (elem) {
        var operator = elem[0];
        if (operator === 'search') {
            // Search terms are the catch-all case.
            // All tokens that don't start with a known operator and
            // a colon are glued together to form a search term.
            return elem[1];
        } else {
            return elem[0] + ':' + encodeOperand(elem[1].toString());
        }
    });
    return parts.join(' ');
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
            // Filter out the "in" keyword and the embedded narrow (if any).
            return value.operator !== 'in' && !(page_params.narrow_stream !== undefined &&
                                                value.operator === "stream" &&
                                                value.operand.toLowerCase() === page_params.narrow_stream.toLowerCase());
        });
        return safe_to_return;
    },

    operands: function Filter_get_operands(operator) {
        return _.chain(this._operators)
            .filter(function (elem) { return elem.operator === operator; })
            .map(function (elem) { return elem.operand; })
            .value();
    },

    has_operand: function Filter_has_operand(operator, operand) {
        return _.any(this._operators, function (elem) {
            return elem.operator === operator && elem.operand === operand;
        });
    },

    has_operator: function Filter_has_operator(operator) {
        return _.any(this._operators, function (elem) {
            return elem.operator === operator;
        });
    },

    is_search: function Filter_is_search() {
        return this.has_operator('search');
    },

    can_apply_locally: function Filter_can_apply_locally() {
        return ! this.is_search();
    },

    _canonicalize_operators: function Filter__canonicalize_operators(operators_mixed_case) {
        return _.map(operators_mixed_case, function (tuple) {
            return Filter.canonicalize_tuple(tuple);
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
            return _.all(operators, function (term) {
                return message_matches_search_term(message, term.operator, term.operand);
            });
        };
    }
};

return Filter;

}());
if (typeof module !== 'undefined') {
    module.exports = Filter;
}
