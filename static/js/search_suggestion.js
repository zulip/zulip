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

function stream_matches_query(stream_name, q) {
    return phrase_match(stream_name, q);
}

function highlight_person(query, person) {
    var hilite = typeahead_helper.highlight_query_in_phrase;
    return hilite(query, person.full_name) + " &lt;" + hilite(query, person.email) + "&gt;";
}

function match_criteria(operators, criteria) {
    var filter = new Filter(operators);
    return _.any(criteria, function (cr) {
        if (_.has(cr, 'operand')) {
            return filter.has_operand(cr.operator, cr.operand);
        }
        return filter.has_operator(cr.operator);
    });
}

function compare_by_huddle(huddle) {
    huddle = _.map(huddle.slice(0, -1), function (person) {
        person = people.get_by_email(person);
        if (person) {
            return person.user_id;
        }
    });

    // Construct dict for all huddles, so we can lookup each's recency
    var huddles = activity.get_huddles();
    var huddle_dict = {};
    for (var i = 0; i < huddles.length; i += 1) {
        huddle_dict[huddles[i]] = i + 1;
    }

    return function (person1, person2) {
        var huddle1 = huddle.concat(person1.user_id).sort().join(',');
        var huddle2 = huddle.concat(person2.user_id).sort().join(',');

        // If not in the dict, assign an arbitrarily high index
        var score1 = huddle_dict[huddle1] || 100;
        var score2 = huddle_dict[huddle2] || 100;
        var diff = score1 - score2;

        if (diff !== 0) {
            return diff;
        }
        return typeahead_helper.compare_by_pms(person1, person2);
    };
}

function get_stream_suggestions(last, operators) {
    if (!(last.operator === 'stream' || last.operator === 'search'
        || last.operator === '')) {
        return [];
    }

    var invalid = [
        {operator: 'stream'},
        {operator: 'is', operand: 'private'},
        {operator: 'pm-with'},
    ];
    if (match_criteria(operators, invalid)) {
        return [];
    }

    var query = last.operand;
    var streams = stream_data.subscribed_streams();

    streams = _.filter(streams, function (stream) {
        return stream_matches_query(stream, query);
    });

    streams = typeahead_helper.sorter(query, streams);

    var objs = _.map(streams, function (stream) {
        var prefix = 'stream';
        var highlighted_stream = typeahead_helper.highlight_with_escaping(query, stream);
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

function get_group_suggestions(all_persons, last, operators) {
    if (last.operator !== 'pm-with' ) {
        return [];
    }

    var invalid = [
        {operator: 'stream'},
    ];
    if (match_criteria(operators, invalid)) {
        return [];
    }

    var operand = last.operand;
    var negated = last.negated;

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
    var parts = all_but_last_part.split(',').concat(people.my_current_email());
    var persons = _.filter(all_persons, function (person) {
        if (_.contains(parts, person.email)) {
            return false;
        }
        return (last_part === '') || people.person_matches_query(person, last_part);
    });

    persons.sort(compare_by_huddle(parts));

    // Take top 15 persons, since they're ordered by pm_recipient_count.
    persons = persons.slice(0, 15);

    var prefix = Filter.operator_to_prefix('pm-with', negated);

    var suggestions = _.map(persons, function (person) {
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

// Possible args for autocomplete_operator: pm-with, sender, from
function get_person_suggestions(all_persons, last, operators, autocomplete_operator) {
    if (last.operator === "is" && last.operand === "private") {
        // Interpret 'is:private' as equivalent to 'pm-with:'
        last = {operator: "pm-with", operand: "", negated: false};
    }

    var query = last.operand;

    // Only accept queries who match the specified operator, or no operator (search)
    if (!(last.operator === 'search' || last.operator === autocomplete_operator)) {
        return [];
    }

    // Be especially strict about the less common "from" operator.
    if (autocomplete_operator === 'from' && last.operator !== 'from') {
        return [];
    }

    var invalid;
    if (autocomplete_operator === 'pm-with') {
        invalid = [{operator: 'pm-with'}, {operator: 'stream'}];
    } else {
        // If not pm-with, then this must either be 'sender' or 'from'
        invalid = [{operator: 'sender'}, {operator: 'from'}];
    }

    if (match_criteria(operators, invalid)) {
        return [];
    }

    var persons = _.filter(all_persons, function (person) {
        return people.person_matches_query(person, query);
    });

    persons.sort(typeahead_helper.compare_by_pms);

    var prefix = Filter.operator_to_prefix(autocomplete_operator, last.negated);

    var objs = _.map(persons, function (person) {
        var name = highlight_person(query, person);
        var description = prefix + ' ' + name;
        var terms = [{
            operator: autocomplete_operator,
            operand: person.email,
            negated: last.negated,
        }];
        if (autocomplete_operator === 'pm-with' && last.negated) {
            // In the special case of '-pm-with', add 'is:private' before it
            // because we assume the user still wants to narrow to PMs
            terms.unshift({operator: 'is', operand: 'private'});
        }
        var search_string = Filter.unparse(terms);
        return {description: description, search_string: search_string};
    });

    return objs;
}

function get_default_suggestion(operators) {
    // Here we return the canonical suggestion for the full query that the
    // user typed.  (The caller passes us the parsed query as "operators".)
    if (operators.length === 0) {
        return {description: '', search_string: ''};
    }
    var search_string = Filter.unparse(operators);
    var description = Filter.describe(operators);
    description = Handlebars.Utils.escapeExpression(description);
    return {description: description, search_string: search_string};
}

function get_topic_suggestions(last, operators) {
    if (last.operator === '') {
        return [];
    }

    var invalid = [
        {operator: 'pm-with'},
        {operator: 'is', operand: 'private'},
        {operator: 'topic'},
    ];

    if (match_criteria(operators, invalid)) {
        return [];
    }

    var operator = Filter.canonicalize_operator(last.operator);
    var operand = last.operand;
    var negated = (operator === 'topic') && (last.negated);
    var stream;
    var guess;
    var filter = new Filter(operators);
    var suggest_operators = [];

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
        guess = '';
        stream = operand;
        suggest_operators.push(last);
        break;
    case 'topic':
    case 'search':
        guess = operand;
        if (filter.has_operator('stream')) {
            stream = filter.operands('stream')[0];
        } else {
            stream = narrow_state.stream();
            suggest_operators.push({operator: 'stream', operand: stream});
        }
        break;
    default:
        return [];
    }

    if (!stream) {
        return [];
    }


    var stream_id = stream_data.get_stream_id(stream);
    if (!stream_id) {
        return [];
    }

    var topics = topic_data.get_recent_names(stream_id);

    if (!topics || !topics.length) {
        return [];
    }

    // Be defensive here in case stream_data.get_recent_topics gets
    // super huge, but still slice off enough topics to find matches.
    topics = topics.slice(0, 300);

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
        var operators = suggest_operators.concat([topic_term]);
        var search_string = Filter.unparse(operators);
        var description = Filter.describe(operators);
        return {description: description, search_string: search_string};
    });
}

function get_operator_subset_suggestions(operators) {
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


function get_special_filter_suggestions(last, operators) {
    var suggestions = [
        {
            search_string: 'is:private',
            description: 'private messages',
            invalid: [
                {operator: 'is', operand: 'private'},
                {operator: 'stream'},
                {operator: 'pm-with'},
                {operator: 'in'},
            ],

        },
        {
            search_string: 'is:starred',
            description: 'starred messages',
            invalid: [
                {operator: 'is', operand: 'starred'},
            ],
        },
        {
            search_string: 'is:mentioned',
            description: '@-mentions',
            invalid: [
                {operator: 'is', operand: 'mentioned'},
            ],
        },
        {
            search_string: 'is:alerted',
            description: 'alerted messages',
            invalid: [
                {operator: 'is', operand: 'alerted'},
            ],
        },
        {
            search_string: 'is:unread',
            description: 'unread messages',
            invalid: [
                {operator: 'is', operand: 'unread'},
            ],
        },
    ];

    var last_string = Filter.unparse([last]).toLowerCase();
    suggestions = _.filter(suggestions, function (s) {
        if (match_criteria(operators, s.invalid)) {
            return false;
        }
        if (last_string === '') {
            return true;
        }
        return (s.search_string.toLowerCase().indexOf(last_string) === 0) ||
               (s.description.toLowerCase().indexOf(last_string) === 0);
    });

    // Only show home if there's an empty bar
    if (operators.length === 0 && last_string === '') {
        suggestions.unshift({search_string: '', description: 'Home'});
    }
    return suggestions;
}

function get_sent_by_me_suggestions(last, operators) {
    var last_string = Filter.unparse([last]).toLowerCase();
    var sender_query = 'sender:' + people.my_current_email();
    var from_query = 'from:' + people.my_current_email();
    var description = 'sent by me';
    var invalid = [
        {operator: 'sender'},
        {operator: 'from'},
    ];

    if (match_criteria(operators, invalid)) {
        return [];
    }

    if (last.operator === '' || sender_query.indexOf(last_string) === 0 ||
        'sender:me'.indexOf(last_string) === 0 || last_string === 'sent') {
        return [
            {
                search_string: sender_query,
                description: description,
            },
        ];
    } else if (from_query.indexOf(last_string) === 0 || 'sender:me'.indexOf(last_string) === 0) {
        return [
            {
                search_string: from_query,
                description: description,
            },
        ];
    }
    return [];
}

function get_containing_suggestions(last) {
        if (!(last.operator === 'search' || last.operator === 'has')) {
            return [];
        }

        var choices = ['link', 'image', 'attachment'];
        choices = _.filter(choices, function (choice) {
            return phrase_match(choice, last.operand);
        });

        return _.map(choices, function (choice) {
            var op = [{operator: 'has', operand: choice, negated: last.negated}];
            var search_string = Filter.unparse(op);
            var description = Filter.describe(op);
            return {description: description, search_string: search_string};
        });
}

function get_operator_suggestions(last) {
        if (!(last.operator === 'search')) {
            return [];
        }

        var negated = false;
        if (last.operand.indexOf("-") === 0) {
            negated = true;
            last.operand = last.operand.slice(1);
        }

        var choices = ['stream', 'topic', 'pm-with', 'sender', 'near', 'has', 'from', 'group-pm-with'];
        choices = _.filter(choices, function (choice) {
            return phrase_match(choice, last.operand);
        });

        return _.map(choices, function (choice) {
            var op = [{operator: choice, operand: '', negated: negated}];
            var search_string = Filter.unparse(op);
            var description = Filter.describe(op);
            return {description: description, search_string: search_string};
        });
}

function attach_suggestions(result, base, suggestions) {
    _.each(suggestions, function (suggestion) {
        if (base.description.length > 0) {
            suggestion.search_string = base.search_string + " " + suggestion.search_string;
            suggestion.description = base.description + ", " + suggestion.description;
        }
        result.push(suggestion);
    });
}

exports.get_suggestions = function (query) {
    // This method works in tandem with the typeahead library to generate
    // search suggestions.  If you want to change its behavior, be sure to update
    // the tests.  Its API is partly shaped by the typeahead library, which wants
    // us to give it strings only, but we also need to return our caller a hash
    // with information for subsequent callbacks.
    var result = [];
    var suggestion;
    var base; //base, default suggestion
    var suggestions;

    // Add an entry for narrow by operators.
    var operators = Filter.parse(query);
    var last = {operator: '', operand: '', negated: false};
    if (operators.length > 0) {
        last = operators.slice(-1)[0];
    }

    // Display the default first
    if (last.operator !== '') {
        suggestion = get_default_suggestion(operators);
        result = [suggestion];
    }

    var base_operators = [];
    if (operators.length > 1) {
        base_operators = operators.slice(0, -1);
    }
    base = get_default_suggestion(base_operators);

    // Get all individual suggestions, and then attach_suggestions
    // mutates the list 'result' to add a properly-formatted suggestion
    suggestions = get_special_filter_suggestions(last, base_operators);
    attach_suggestions(result, base, suggestions);

    suggestions = get_sent_by_me_suggestions(last, base_operators);
    attach_suggestions(result, base, suggestions);

    suggestions = get_stream_suggestions(last, base_operators);
    attach_suggestions(result, base, suggestions);

    var persons = people.get_all_persons();

    suggestions = get_person_suggestions(persons, last, base_operators, 'pm-with');
    attach_suggestions(result, base, suggestions);

    suggestions = get_person_suggestions(persons, last, base_operators, 'sender');
    attach_suggestions(result, base, suggestions);

    suggestions = get_person_suggestions(persons, last, base_operators, 'from');
    attach_suggestions(result, base, suggestions);

    suggestions = get_person_suggestions(persons, last, base_operators, 'group-pm-with');
    attach_suggestions(result, base, suggestions);

    suggestions = get_group_suggestions(persons, last, base_operators);
    attach_suggestions(result, base, suggestions);

    suggestions = get_topic_suggestions(last, base_operators);
    attach_suggestions(result, base, suggestions);

    suggestions = get_operator_suggestions(last);
    attach_suggestions(result, base, suggestions);

    suggestions = get_containing_suggestions(last);
    attach_suggestions(result, base, suggestions);

    suggestions = get_operator_subset_suggestions(operators);
    result = result.concat(suggestions);

    _.each(result, function (sug) {
        var first = sug.description.charAt(0).toUpperCase();
        sug.description = first + sug.description.slice(1);
    });

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
