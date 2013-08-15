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
            return [Filter.canonicalize_operator(operator[0]),
                    stream_data.canonicalized_name(operator[1])];
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

return Filter;

}());
if (typeof module !== 'undefined') {
    module.exports = Filter;
}
