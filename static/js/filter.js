var Filter = (function () {

// Needs note for what messages and operands are
// Also more information about the Filter class

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

    return related_regexp.test(message.subject);
}

function message_in_home(message) {
    /*
    message_in_home
    Argument:
        message /TODO
    Return value:
        /TODO
    */
    if (message.type === "private" || message.mentioned ||
        (page_params.narrow_stream !== undefined &&
         message.stream.toLowerCase() === page_params.narrow_stream.toLowerCase())) {
        return true;
    }

    return stream_data.in_home_view(message.stream_id);
}

function message_matches_search_term(message, operator, operand) {
    /*
    message_matches_search_term
    Argument:
        message /TODO
        operator (string in ['is', 'in', 'near', 'id', 'stream', 'topic',
            'sender', 'pm-with']
                'is': return true if message meets the condition in the operand
                    (private, starred, mentioned or alerted)
                'in': return true if message is in home view,
                'near': /TODO
                'id': return true if message's id matches operand
                'stream': return true if message is in the stream 
                    specified by the operand
                'topic': return true if message's topic matches the operand
                'sender': /TODO
                'pm-with': /TODO
        operand (string): the "search term"
    Return value:
        True if /TODO
        False if /TODO
    */
    switch (operator) {
    case 'is':
        if (operand === 'private') {
            return (message.type === 'private');
        } else if (operand === 'starred') {
            return message.starred;
        } else if (operand === 'mentioned') {
            return message.mentioned;
        } else if (operand === 'alerted') {
            return message.alerted;
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
        return (message.id.toString() === operand);

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
            return (message.stream_id === stream_id);
        }

        // We need this fallback logic in case we have a message
        // loaded for a stream that we are no longer
        // subscribed to (or that was deleted).
        return (message.stream.toLowerCase() === operand);

    case 'topic':
        if (message.type !== 'stream') {
            return false;
        }

        operand = operand.toLowerCase();
        if (page_params.realm_is_zephyr_mirror_realm) {
            return zephyr_topic_name_match(message, operand);
        }
        return (message.subject.toLowerCase() === operand);


    case 'sender':
        return people.id_matches_email_operand(message.sender_id, operand);

    case 'pm-with':
        // TODO: use user_ids, not emails here
        if (message.type !== 'private') {
            return false;
        }
        var operand_ids = people.pm_with_operand_ids(operand);
        if (!operand_ids) {
            return false;
        }
        var message_ids = people.pm_with_user_ids(message);
        if (!message_ids) {
            return false;
        }

        return _.isEqual(operand_ids, message_ids);
    }

    return true; // unknown operators return true (effectively ignored)
}


function Filter(operators) {
    /*
    /TODO
    */
    if (operators === undefined) {
        this._operators = [];
    } else {
        this._operators = this._canonicalize_operators(operators);
    }
}

var canonical_operators = {from: "sender", subject: "topic"};
// TODO

Filter.canonicalize_operator = function (operator) {
    /*
    canonicalize_operator
    Argument:
        operator (string)
    Return value:
        If operator is a key in canonical_operators, it
        is an alias of a canonical operator and the function
        returns its corresponding canon operator's name
        Otherwise returns the original operator in all
        lower case
    */
    operator = operator.toLowerCase();
    if (canonical_operators.hasOwnProperty(operator)) {
        return canonical_operators[operator];
    }
    return operator;
};

Filter.canonicalize_term = function (term) {
    /*
    canonicalize_term
    standardize the search terms as followed:
        - canonicalize the operators (toLowerCase and
        turn aliases into canonical operators)
        - if the operand refers to a person, substitute the
        person name with their email address 
        - toLowerCase the operand
        - replace curly quotes with standard quotes
        - for the 'has' operator, make the operand singular

    Argument:
        term (object): has 3 keys:
            negated : true | if match to be excluded, false to in included
            operator : string | the operator
            operand : string | the operand for this operator
    Return value:
        (obj) with 3 keys as in argument, but standardized as outlined above

    */
    var negated = term.negated;
    var operator = term.operator;
    var operand = term.operand;

    // Make negated be explictly false for both clarity and
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

// TODO
function encodeOperand(operand) {
    return operand.replace(/%/g,  '%25')
                  .replace(/\+/g, '%2B')
                  .replace(/ /g,  '+');
}

function decodeOperand(encoded, operator) {
    if (operator !== 'pm-with' && operator !== 'sender' && operator !== 'from') {
        encoded = encoded.replace(/\+/g, ' ');
    }
    return util.robust_uri_decode(encoded);
}

// Parse a string into a list of operators (see below).
Filter.parse = function (str) {
    /*
    parse
    Argument:
        str (string): the full search string as entered by user from the search bar
    Return value:
        operators (array[obj]) an array of token objects, where earch objects has
            the following keys:
                negated (boolean) : true if searching to exclude, false if searching to include
                operator (string) : the operator, e.g. 'stream', 'is'
                operand (string) : the operand to apply on the operator
                If a token doesn't contain any operator, the token is treated as part of the
                operand for the search operator
    */
    var operators   = [];
    var search_term = [];
    var negated; // True if the operator is prefixed with '-', to denote exclusion
    var operator;
    var operand;
    var term;

    // TODO: what is this for?
    var matches = str.match(/"[^"]+"|\S+/g); // look at the "fluffy bunny" // "fluffy bunny // what about \"
    if (matches === null) {
        return operators;
    }
    _.each(matches, function (token) {
        var parts;
        var operator;
        parts = token.split(':');
        // If no ':' (parts.length === 1)
        // Why token[0] === '"'? Is that to escape a later ':'?
        // If there are a valid operator with several ':'s, e.g
        // stream:foo:bar, does it treat the operand as foo:bar?
        if (token[0] === '"' || parts.length === 1) {
            // Looks like a normal search term.
            search_term.push(token);
        } else {
            // Looks like an operator.
            // Get the first part before ':' and make that the operator
            // Check if it's negated, set negated = true and correct
            // the operator if so
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

       ['subject', 'my amazing subject']

   These are not keys in a JavaScript object, because we
   might need to support multiple operators of the same type.
*/
Filter.unparse = function (operators) {
    /*
    The opposite of parse. What is this used for?
    */
    var parts = _.map(operators, function (elem) {

        if (elem.operator === 'search') {
            // Search terms are the catch-all case.
            // All tokens that don't start with a known operator and
            // a colon are glued together to form a search term.
            return elem.operand;
        }
        var sign = elem.negated ? '-' : '';
        return sign + elem.operator + ':' + encodeOperand(elem.operand.toString());
    });
    return parts.join(' ');
};



Filter.prototype = {
    predicate: function Filter_predicate() {
        /*
        predicate
        Get back a function that takes a message object as input and checks
        whether that message fits the narrow of this filter.
        Argument: none
        Return value:
            Function (message) => {
                return true if message fits the critieria of this filter
                return false otherwise
            }
        */
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
            // Filter out the embedded narrow (if any).
            return !(page_params.narrow_stream !== undefined &&
                     value.operator === "stream" &&
                     value.operand.toLowerCase() === page_params.narrow_stream.toLowerCase());
        });
        return safe_to_return;
    },

    operands: function Filter_get_operands(operator) {
        return _.chain(this._operators)
            .filter(function (elem) { return !elem.negated && (elem.operator === operator); })
            .map(function (elem) { return elem.operand; })
            .value();
    },

    has_operand: function Filter_has_operand(operator, operand) {
        /*
        has_operand
        Check if the search query has a particular operator / operand pair.
        Arguments:
            operator (string): the string representing an operator e.g. 'stream'
            operand (string): the value to search for with that operator
        Return value:
            true if the operator / operand pair exists in this search condition
            and negated is false (search meant to include, not exclude this pair)
            false otherwise
        */
        return _.any(this._operators, function (elem) {
            return !elem.negated && (elem.operator === operator && elem.operand === operand);
        });
    },

    has_operator: function Filter_has_operator(operator) {
        /*
        has_operator
        Check if the search query has a particular operator.
        Argument:
            operator (string): the string representing an operator e.g. 'stream'
        Return value:
            true if the search query for this Filter instance contains that operator
            false otherwise
        */
        return _.any(this._operators, function (elem) {
            if (elem.negated && (!_.contains(['search', 'has'], elem.operator))) {
                return false;
            }
            return elem.operator === operator;
        });
    },

    is_search: function Filter_is_search() {
        /*
        is_search
        Check if 'search' is one of the operators for this search query.
        Argument: none
        Return value:
            true if search is an operator, false otherwise
        */
        return this.has_operator('search');
    },

    can_apply_locally: function Filter_can_apply_locally() {
        /*
        can_apply_locally
        Check if the search can be done without calling the backend.
        Argument: none
        return value:
            true if the search query doesn't include the operators
            'search' or 'has' (effectively means the filtering can
            happen exclusively on the front end)
        */
        return (!this.is_search()) && (!this.has_operator('has'));
    },

    _canonicalize_operators: function Filter__canonicalize_operators(operators_mixed_case) {
        /*
        _canonicalize_operators
        Arugment:
            operators_mixed_case /TODO
        Return value:
            /TODO
        */
        return _.map(operators_mixed_case, function (tuple) {
            return Filter.canonicalize_term(tuple);
        });
    },

    filter_with_new_topic: function Filter_filter_with_new_topic(new_topic) {
        var terms = _.map(this._operators, function (term) {
            var new_term = _.clone(term);
            if (new_term.operator === 'topic' && !new_term.negated) {
                new_term.operand = new_topic;
            }
            return new_term;
        });
        return new Filter(terms);
    },

    has_topic: function Filter_has_topic(stream_name, topic) {
        /*
        has_topic
        Check if the search query includes a narrowed search in a particular topic.
        Argument:
            stream_name (string) name of the stream that the topic should be in 
            topic (string) name of the topic
        Return value:
            true if the search query includes both a narrowing down to stream_name 
            by stream, and topic by topic
            false otherwise
        // TODO: do we want to tie topic searches to a particular stream? or all streams?
        */
        return this.has_operand('stream', stream_name) && this.has_operand('topic', topic);
    },

    update_email: function (user_id, new_email) {
        _.each(this._operators, function (term) {
            switch (term.operator) {
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
                var ok = message_matches_search_term(message, term.operator, term.operand);
                if (term.negated) {
                    ok = !ok;
                }
                return ok;
            });
        };
    },
};

Filter.operator_to_prefix = function (operator, negated) {
    /*
    Filter.operator_to_prefix
    Translates operators to types of suggestions displayed in the suggestion dropdown
    when the operator is not 'is'
    Arguments: 
        operator(string): can be 'stream', 'near', 'has', 'id', 'subject', 'topic',
            'from', 'sender', 'pm-with', 'in'
    Return value:
        (string): the string to show in the dropdown
    */
    var verb;

    if (operator === 'search') {
        return negated ? 'Exclude' : 'Search for';
    }

    verb = negated ? 'Exclude ' : 'Narrow to ';

    switch (operator) {
    case 'stream':
        return verb + 'stream';

    case 'near':
        return verb + 'messages around';

    case 'has':
        return verb + 'messages with one or more';

    case 'id':
        return verb + 'message ID';

    case 'subject':
    case 'topic':
        return verb + 'topic';

    case 'from':
    case 'sender':
        return verb + 'messages sent by';

    case 'pm-with':
        return verb + 'private messages with';

    case 'in':
        return verb + 'messages in';

    // Note: We hack around using this in "describe" below.
    case 'is':
        return verb + 'messages that are';
    }
    return '';
};

// Convert a list of operators to a human-readable description.
Filter.describe = function (operators) {
    /*
    Filter.describe
    Argument:
        operators(array[string]): array contains all operators present in
            a search
    Return value:
    */
    // If the search string is empty, then the description is "Go to Home view"
    if (operators.length === 0) {
        return 'Go to Home view';
    }

    var parts = [];

    // If there are more than two operators
    if (operators.length >= 2) {
        var is = function (term, expected) {
            // TODO ???
            return (term.operator === expected) && !term.negated;
        };
        // If the first operator is "stream" and the second is "topic"
        // describe the search as 'Narrow to stream > topic'
        // And then remove the first two terms
        // TODO: need more consistent nomenclature, term / operator is
        // confusing
        if (is(operators[0], 'stream') && is(operators[1], 'topic')) {
            var stream = operators[0].operand;
            var topic = operators[1].operand;
            var part = 'Narrow to ' + stream + ' > ' + topic;
            parts = [part];
            operators = operators.slice(2);
        }
    }

    // If there is exaclty one operator
    var more_parts = _.map(operators, function (elem) {
        var operand = elem.operand;
        var canonicalized_operator = Filter.canonicalize_operator(elem.operator);
        // and that operator is 'is', return the corresponding description
        // e.g 'Narrow to all private messages'
        if (canonicalized_operator ==='is') {
            var verb = elem.negated ? 'Exclude ' : 'Narrow to ';
            if (operand === 'private') {
                return verb + 'all private messages';
            } else if (operand === 'starred') {
                return verb + 'starred messages';
            } else if (operand === 'mentioned') {
                return verb + 'mentioned messages';
            } else if (operand === 'alerted') {
                return verb + 'alerted messages';
            }
        } else {
            // If it's not 'is', we use prefix_for_operator to look up
            // the description
            var prefix_for_operator = Filter.operator_to_prefix(canonicalized_operator,
                                                                elem.negated);
            if (prefix_for_operator !== '') {
                return prefix_for_operator + ' ' + operand;
            }
        }
        // if we don't recognize the operator then the description is
        // 'Narrow to (unknown operator)'
        // TODO???
        return 'Narrow to (unknown operator)';
    });
    // Concat all descriptions, separated by coma, to form the final description
    return parts.concat(more_parts).join(', ');
};


return Filter;

}());
if (typeof module !== 'undefined') {
    module.exports = Filter;
}
