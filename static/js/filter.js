var Filter = (function () {

function message_in_home(message) {
    if (message.type === "private") {
        return true;
    }

    return stream_data.in_home_view(message.stream);
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
    default:
        operand = operand.toString().toLowerCase();
    }

    // We may want to consider allowing mixed-case operators at some point
    return [operator, operand];
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

// Parse a string into a list of operators (see below).
Filter.parse = function (str) {
    var operators   = [];
    var search_term = [];
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
            operators.push([operator, decodeOperand(parts.join(':'))]);
        }
    });
    // NB: Callers of 'parse' can assume that the 'search' operator is last.
    if (search_term.length > 0) {
        operators.push(['search', search_term.join(' ')]);
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
                        return message_in_home(message);
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

                    operand = operand.toLowerCase();
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

                    operand = operand.toLowerCase();
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

return Filter;

}());
if (typeof module !== 'undefined') {
    module.exports = Filter;
}
