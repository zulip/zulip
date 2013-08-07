var search_suggestion = (function () {

var exports = {};

function phrase_match(phrase, q) {
    // match "tes" to "test" and "stream test" but not "hostess"
    var i;
    q = q.toLowerCase();

    phrase = phrase.toLowerCase();
    if (phrase.indexOf(q) === 0) {
        return true;
    }

    var parts = phrase.split(' ');
    for (i = 0; i < parts.length; i++) {
        if (parts[i].indexOf(q) === 0) {
            return true;
        }
    }
    return false;
}

function person_matches_query(person, q) {
    return phrase_match(person.full_name, q) || phrase_match(person.email, q);
}

function stream_matches_query(stream_name, q) {
    return phrase_match(stream_name, q);
}

// Convert a list of operators to a human-readable description.
function describe(operators) {
    if (operators.length === 0) {
        return 'Go to Home view';
    }

    var parts = [];

    if (operators.length >= 2) {
        if (operators[0][0] === 'stream' && operators[1][0] === 'topic') {
            var stream = operators[0][1];
            var topic = operators[1][1];
            var part = 'Narrow to ' + stream + ' > ' + topic;
            parts = [part];
            operators = operators.slice(2);
        }
    }

    var more_parts = _.map(operators, function (elem) {
        var operand = elem[1];
        switch (narrow.canonicalize_operator(elem[0])) {
        case 'is':
            if (operand === 'private') {
                return 'Narrow to all private messages';
            } else if (operand === 'starred') {
                return 'Narrow to starred messages';
            } else if (operand === 'mentioned') {
                return 'Narrow to mentioned messages';
            }
            break;

        case 'stream':
            return 'Narrow to stream ' + operand;

        case 'near':
            return 'Narrow to messages around ' + operand;

        case 'id':
            return 'Narrow to message ID ' + operand;

        case 'topic':
            return 'Narrow to topic ' + operand;

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
    });
    return parts.concat(more_parts).join(', ');
}

function highlight_person(query, person) {
    var hilite = typeahead_helper.highlight_query_in_phrase;
    return hilite(query, person.full_name) + " &lt;" + hilite(query, person.email) + "&gt;";
}

function get_stream_suggestions(operators) {
    var query;

    switch (operators.length) {
    case 0:
        query = '';
        break;
    case 1:
        var operand = operators[0][0];
        query = operators[0][1];
        if (!(operand === 'stream' || operand === 'search')) {
            return [];
        }
        break;
    default:
        return [];
    }

    var streams = subs.subscribed_streams();

    streams = _.filter(streams, function (stream) {
        return stream_matches_query(stream, query);
    });

    streams = typeahead_helper.sorter(query, streams);

    var objs = _.map(streams, function (stream) {
        var prefix = 'Narrow to stream';
        var highlighted_stream = typeahead_helper.highlight_query_in_phrase(query, stream);
        var description = prefix + ' ' + highlighted_stream;
        var search_string = narrow.unparse([['stream', stream]]);
        return {description: description, search_string: search_string};
    });

    return objs;
}

function get_private_suggestions(all_people, operators) {
    if (operators.length === 0) {
        return [];
    }

    var ok = false;
    if ((operators[0][0] === 'is') && (operators[0][1] === 'private')) {
        operators = operators.slice(1);
        ok = true;
    } else if (operators[0][0] === 'pm-with') {
        ok = true;
    }

    if (!ok) {
        return [];
    }

    var query;

    if (operators.length === 0) {
        query = '';
    } else if (operators.length === 1) {
        var operator = operators[0][0];
        if (operator === 'search' || operator === 'pm-with') {
            query = operators[0][1];
        }
        else {
            return [];
        }
    }
    else {
        return [];
    }


    var people = _.filter(all_people, function (person) {
        return (query === '') || person_matches_query(person, query);
    });

    people.sort(typeahead_helper.compare_by_pms);

    // Take top 15 people, since they're ordered by pm_recipient_count.
    people = people.slice(0, 15);

    var suggestions = _.map(people, function (person) {
        var name = highlight_person(query, person);
        var description = 'Narrow to private messages with ' + name;
        var search_string = narrow.unparse([['pm-with', person.email]]);
        return {description: description, search_string: search_string};
    });

    suggestions.push({
        search_string: 'is:private',
        description: 'Private messages'
    });

    return suggestions;
}

function get_person_suggestions(all_people, query, prefix, operator) {
    if (query === '') {
        return [];
    }

    var people = _.filter(all_people, function (person) {
        return person_matches_query(person, query);
    });

    people.sort(typeahead_helper.compare_by_pms);

    var objs = _.map(people, function (person) {
        var name = highlight_person(query, person);
        var description = prefix + ' ' + name;
        var search_string = operator + ':' + person.email;
        return {description: description, search_string: search_string};
    });

    return objs;
}

function get_default_suggestion(operators) {
    // Here we return the canonical suggestion for the full query that the
    // user typed.  (The caller passes us the parsed query as "operators".)
    var search_string = narrow.unparse(operators);
    var description = describe(operators);
    description = Handlebars.Utils.escapeExpression(description);
    return {description: description, search_string: search_string};
}

function get_topic_suggestions(query_operators) {
    if (query_operators.length === 0) {
        return [];
    }

    var last_term = query_operators.slice(-1)[0];
    var operator = narrow.canonicalize_operator(last_term[0]);
    var operand = last_term[1];
    var stream;
    var guess;
    var filter;

    // stream:Rome -> show all Rome topics
    // stream:Rome topic: -> show all Rome topics
    // stream:Rome f -> show all Rome topics with a word starting in f
    // stream:Rome topic:f -> show all Rome topics with a word starting in f
    // stream:Rome topic:f -> show all Rome topics with a word starting in f

    // When narrowed to a stream:
    //   topic: -> show all topics in current stream
    //   foo -> show all topics in current stream with words starting with foo

    // If somebody explicitly types search:, then we might
    // not want to suggest topics, but I feel this is a very
    // minor issue, and narrow.parse() is currently lossy
    // in terms of telling us whether they provided the operator,
    // i.e. "foo" and "search:foo" both become [['search', 'foo']].
    switch (operator) {
    case 'stream':
        filter = new narrow.Filter(query_operators);
        if (filter.has_operator('topic')) {
            return [];
        }
        guess = '';
        stream = operand;
        break;
    case 'topic':
    case 'search':
        guess = operand;
        query_operators = query_operators.slice(0, -1);
        filter = new narrow.Filter(query_operators);
        if (filter.has_operator('topic')) {
            return [];
        }
        if (filter.has_operator('stream')) {
            stream = filter.operands('stream')[0];
        } else {
            stream = narrow.stream();
            query_operators.push(['stream', stream]);
        }
        break;
    default:
        return [];
    }

    if (!stream) {
        return [];
    }

    stream = subs.canonicalized_name(stream);

    var topics = recent_subjects.get(stream);

    if (!topics) {
        return [];
    }

    // Be defensive here in case recent_subjects gets super huge, but
    // still slice off enough topics to find matches.
    topics = topics.slice(0, 300);

    topics = _.map(topics, function (topic) {
        return topic.subject; // "subject" is just the name of the topic
    });

    topics = topics.slice(0, 10);

    if (guess !== '') {
        topics = _.filter(topics, function (topic) {
            return phrase_match(topic, guess);
        });
    }

    // Just use alphabetical order.  While recency and read/unreadness of
    // subjects do matter in some contexts, you can get that from the left sidebar,
    // and I'm leaning toward high scannability for autocompletion.  I also don't
    // care about case.
    topics.sort();

    return _.map(topics, function (topic) {
        var topic_operator = ['topic', topic];
        var operators = query_operators.concat([topic_operator]);
        var search_string = narrow.unparse(operators);
        var description = describe(operators);
        return {description: description, search_string: search_string};
    });
}

function get_operator_subset_suggestions(query, operators) {
    // For stream:a topic:b search:c, suggest:
    //  stream:a topic:b
    //  stream:a
    if (operators.length < 1) {
        return [];
    }

    var i;
    var suggestions = [];

    for (i = operators.length - 1; i >= 1; --i) {
        var subset = operators.slice(0, i);
        var search_string = narrow.unparse(subset);
        var description = describe(subset);
        var suggestion = {description: description, search_string: search_string};
        suggestions.push(suggestion);
    }

    return suggestions;
}


function get_special_filter_suggestions(query, operators) {
    if (operators.length >= 2) {
        return [];
    }

    var suggestions = [
        {
            search_string: '',
            description: 'Home'
        },
        {
            search_string: 'in:all',
            description: 'All messages'
        },
        {
            search_string: 'is:private',
            description: 'Private messages'
        },
        {
            search_string: 'is:starred',
            description: 'Starred messages'
        },
        {
            search_string: 'is:mentioned',
            description: '@-mentions'
        },
        {
            search_string: 'sender:' + page_params.email,
            description: 'Sent by me'
        }
    ];

    query = query.toLowerCase();

    suggestions = _.filter(suggestions, function (s) {
        if (s.search_string.toLowerCase() === query) {
            return false; // redundant
        }
        if (query === '') {
            return true;
        }
        return (s.search_string.toLowerCase().indexOf(query) === 0) ||
               (s.description.toLowerCase().indexOf(query) === 0);
    });

    return suggestions;
}

exports.get_suggestions = function (query) {
    // This method works in tandem with the typeahead library to generate
    // search suggestions.  If you want to change its behavior, be sure to update
    // the tests.  Its API is partly shaped by the typeahead library, which wants
    // us to give it strings only, but we also need to return our caller a hash
    // with information for subsequent callbacks.
    var result = [];
    var suggestion;
    var suggestions;

    // Add an entry for narrow by operators.
    var operators = narrow.parse(query);
    suggestion = get_default_suggestion(operators);
    result = [suggestion];

    suggestions = get_special_filter_suggestions(query, operators);
    result = result.concat(suggestions);

    suggestions = get_stream_suggestions(operators);
    result = result.concat(suggestions);

    var people = page_params.people_list;

    suggestions = get_person_suggestions(people, query, 'Narrow to private messages with', 'pm-with');
    result = result.concat(suggestions);

    suggestions = get_person_suggestions(people, query, 'Narrow to messages sent by', 'sender');
    result = result.concat(suggestions);

    suggestions = get_private_suggestions(people, operators);
    result = result.concat(suggestions);

    suggestions = get_topic_suggestions(operators);
    result = result.concat(suggestions);

    suggestions = get_operator_subset_suggestions(query, operators);
    result = result.concat(suggestions);

    // Typeahead expects us to give it strings, not objects, so we maintain our own hash
    // back to our objects, and we also filter duplicates here.
    var lookup_table = {};
    var unique_suggestions = [];
    _.each(result, function (obj) {
        if (!lookup_table[obj.search_string]) {
            lookup_table[obj.search_string] = obj;
            unique_suggestions.push(obj);
        }
    });
    var strings = _.map(unique_suggestions, function (obj) {
        return obj.search_string;
    });
    return {
        strings: strings,
        lookup_table: lookup_table
    };
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = search_suggestion;
}
