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
    for (i = 0; i < parts.length; i += 1) {
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
        var operator = operators[0].operator;
        query = operators[0].operand;
        if (!(operator === 'stream' || operator === 'search')) {
            return [];
        }
        break;
    default:
        return [];
    }

    var streams = stream_data.subscribed_streams();

    streams = _.filter(streams, function (stream) {
        return stream_matches_query(stream, query);
    });

    streams = typeahead_helper.sorter(query, streams);

    var objs = _.map(streams, function (stream) {
        var prefix = 'Narrow to stream';
        var highlighted_stream = typeahead_helper.highlight_query_in_phrase(query, stream);
        var description = prefix + ' ' + highlighted_stream;
        var term = {
            operator: 'stream',
            operand: stream,
        };
        var search_string = Filter.unparse([term]);
        return {description: description, search_string: search_string};
    });

    return objs;
}

function get_private_suggestions(all_people, operators, person_operator_matches) {
    if (operators.length === 0) {
        return [];
    }

    var ok = false;
    if ((operators[0].operator === 'is') && (operators[0].operand === 'private')) {
        operators = operators.slice(1);
        ok = true;
    } else  {
        _.each(person_operator_matches, function (item) {
            if (operators[0].operator === item) {
                ok = true;
            }
        });
    }

    if (!ok) {
        return [];
    }

    var query;
    var matching_operator;
    var negated = false;

    if (operators.length === 0) {
        query = '';
        matching_operator = person_operator_matches[0];
    } else if (operators.length === 1) {
        var operator = operators[0].operator;

        if (operator === 'search') {
            query = operators[0].operand;
            matching_operator = person_operator_matches[0];
        } else {
            _.each(person_operator_matches, function (item) {
                if (operator === item) {
                    query = operators[0].operand;
                    matching_operator = item;
                    negated = operators[0].negated;
                }
            });
        }

        if (query === undefined) {
            return [];
        }
    } else {
        return [];
    }


    var people = _.filter(all_people, function (person) {
        return (query === '') || person_matches_query(person, query);
    });

    people.sort(typeahead_helper.compare_by_pms);

    // Take top 15 people, since they're ordered by pm_recipient_count.
    people = people.slice(0, 15);

    var prefix = Filter.operator_to_prefix(matching_operator, negated);

    var suggestions = _.map(people, function (person) {
        var term = {
            operator: matching_operator,
            operand: person.email,
            negated: negated,
        };
        var name = highlight_person(query, person);
        var description = prefix + ' ' + name;
        var terms = [term];
        if (negated) {
            terms = [{operator: 'is', operand: 'private'}, term];
        }
        var search_string = Filter.unparse(terms);
        return {description: description, search_string: search_string};
    });

    suggestions.push({
        search_string: 'is:private',
        description: 'Private messages',
    });

    return suggestions;
}

function get_group_suggestions(all_people, operators) {
    if (operators.length === 0) {
        return [];
    }

    if ((operators[0].operator === 'is') && (operators[0].operand === 'private')) {
        operators = operators.slice(1);
    }

    if (operators.length !== 1 || operators[0].operator !== 'pm-with') {
        return [];
    }

    var operand = operators[0].operand;
    var negated = operators[0].negated;

    // The operand has the form "part1,part2,pa", where all but the last part
    // are emails, and the last part is an arbitrary query.
    //
    // We only generate group suggestions when there's more than one part, and
    // we only use the last part to generate suggestions.
    var all_but_last_part;
    var last_part;

    var last_comma_index = operand.lastIndexOf(',');
    if (last_comma_index < 0) {
        return [];
    }

    // Neither all_but_last_part nor last_part include the final comma.
    all_but_last_part = operand.slice(0, last_comma_index);
    last_part = operand.slice(last_comma_index + 1);

    // We don't suggest a person if their email is already present in the
    // operand (not including the last part).
    var parts = all_but_last_part.split(',');
    var people = _.filter(all_people, function (person) {
        if (_.contains(parts, person.email)) {
            return false;
        }
        return (last_part === '') || person_matches_query(person, last_part);
    });

    people.sort(typeahead_helper.compare_by_pms);

    // Take top 15 people, since they're ordered by pm_recipient_count.
    people = people.slice(0, 15);

    var prefix = Filter.operator_to_prefix('pm-with', negated);

    var suggestions = _.map(people, function (person) {
        var term = {
            operator: 'pm-with',
            operand: all_but_last_part + ',' + person.email,
            negated: negated,
        };
        var name = highlight_person(last_part, person);
        var description = prefix + ' ' + all_but_last_part + ',' + name;
        var terms = [term];
        if (negated) {
            terms = [{operator: 'is', operand: 'private'}, term];
        }
        var search_string = Filter.unparse(terms);
        return {description: description, search_string: search_string};
    });

    return suggestions;
}

function get_person_suggestions(all_people, query, autocomplete_operator) {
    if (query === '') {
        return [];
    }

    var people = _.filter(all_people, function (person) {
        return person_matches_query(person, query);
    });

    people.sort(typeahead_helper.compare_by_pms);

    var prefix = Filter.operator_to_prefix(autocomplete_operator);

    var objs = _.map(people, function (person) {
        var name = highlight_person(query, person);
        var description = prefix + ' ' + name;
        var search_string = autocomplete_operator + ':' + person.email;
        return {description: description, search_string: search_string};
    });

    return objs;
}

function get_default_suggestion(operators) {
    // Here we return the canonical suggestion for the full query that the
    // user typed.  (The caller passes us the parsed query as "operators".)
    var search_string = Filter.unparse(operators);
    var description = Filter.describe(operators);
    description = Handlebars.Utils.escapeExpression(description);
    return {description: description, search_string: search_string};
}

function get_topic_suggestions(query_operators) {
    if (query_operators.length === 0) {
        return [];
    }

    var last_term = query_operators.slice(-1)[0];
    var operator = Filter.canonicalize_operator(last_term.operator);
    var operand = last_term.operand;
    var negated = (operator === 'topic') && (last_term.negated);
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
    // minor issue, and Filter.parse() is currently lossy
    // in terms of telling us whether they provided the operator,
    // i.e. "foo" and "search:foo" both become [{operator: 'search', operand: 'foo'}].
    switch (operator) {
    case 'stream':
        filter = new Filter(query_operators);
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
        filter = new Filter(query_operators);
        if (filter.has_operator('topic')) {
            return [];
        }
        if (filter.has_operator('stream')) {
            stream = filter.operands('stream')[0];
        } else {
            stream = narrow_state.stream();
            query_operators.push({operator: 'stream', operand: stream});
        }
        break;
    default:
        return [];
    }

    if (!stream) {
        return [];
    }

    var topics = stream_data.get_recent_topics(stream);

    stream = stream_data.get_name(stream);

    if (!topics) {
        return [];
    }

    // Be defensive here in case stream_data.get_recent_topics gets
    // super huge, but still slice off enough topics to find matches.
    topics = topics.slice(0, 300);

    topics = _.map(topics, function (topic) {
        return topic.subject; // "subject" is just the name of the topic
    });

    if (guess !== '') {
        topics = _.filter(topics, function (topic) {
            return phrase_match(topic, guess);
        });
    }

    topics = topics.slice(0, 10);

    // Just use alphabetical order.  While recency and read/unreadness of
    // topics do matter in some contexts, you can get that from the left sidebar,
    // and I'm leaning toward high scannability for autocompletion.  I also don't
    // care about case.
    topics.sort();

    return _.map(topics, function (topic) {
        var topic_term = {operator: 'topic', operand: topic, negated: negated};
        var operators = query_operators.concat([topic_term]);
        var search_string = Filter.unparse(operators);
        var description = Filter.describe(operators);
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

    for (i = operators.length - 1; i >= 1; i -= 1) {
        var subset = operators.slice(0, i);
        var search_string = Filter.unparse(subset);
        var description = Filter.describe(subset);
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
            description: 'Home',
        },
        {
            search_string: 'in:all',
            description: 'All messages',
        },
        {
            search_string: 'is:private',
            description: 'Private messages',
        },
        {
            search_string: 'is:starred',
            description: 'Starred messages',
        },
        {
            search_string: 'is:mentioned',
            description: '@-mentions',
        },
        {
            search_string: 'is:alerted',
            description: 'Alerted messages',
        },
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

function get_sent_by_me_suggestions(query, operators) {
    if (operators.length >= 2) {
        return [];
    }

    var sender_query = 'sender:' + people.my_current_email();
    var from_query = 'from:' + people.my_current_email();
    var description = 'Sent by me';

    query = query.toLowerCase();

    if (query === sender_query || query === from_query) {
        return [];
    } else if (query === '' ||
        sender_query.indexOf(query) === 0 ||
        description.toLowerCase().indexOf(query) === 0) {
        return [
            {
                search_string: sender_query,
                description: description,
            },
        ];
    } else if (from_query.indexOf(query) === 0) {
        return [
            {
                search_string: from_query,
                description: description,
            },
        ];
    }
    return [];
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
    var operators = Filter.parse(query);
    suggestion = get_default_suggestion(operators);
    result = [suggestion];

    suggestions = get_special_filter_suggestions(query, operators);
    result = result.concat(suggestions);

    suggestions = get_sent_by_me_suggestions(query, operators);
    result = result.concat(suggestions);

    suggestions = get_stream_suggestions(operators);
    result = result.concat(suggestions);

    var persons = people.get_all_persons();

    suggestions = get_person_suggestions(persons, query, 'pm-with');
    result = result.concat(suggestions);

    suggestions = get_person_suggestions(persons, query, 'sender');
    result = result.concat(suggestions);

    suggestions = get_group_suggestions(persons, operators);
    result = result.concat(suggestions);

    suggestions = get_private_suggestions(persons, operators, ['pm-with', 'sender', 'from']);
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
        lookup_table: lookup_table,
    };
};


return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = search_suggestion;
}
