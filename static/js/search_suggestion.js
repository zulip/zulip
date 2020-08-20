"use strict";

const Handlebars = require("handlebars/runtime");

const huddle_data = require("./huddle_data");
const people = require("./people");
const settings_data = require("./settings_data");

exports.max_num_of_search_results = 12;

function stream_matches_query(stream_name, q) {
    return common.phrase_match(q, stream_name);
}

function make_person_highlighter(query) {
    const hilite = typeahead_helper.make_query_highlighter(query);

    return function (person) {
        if (settings_data.show_email()) {
            return hilite(person.full_name) + " &lt;" + hilite(person.email) + "&gt;";
        }
        return hilite(person.full_name);
    };
}

function match_criteria(operators, criteria) {
    const filter = new Filter(operators);
    return criteria.some((cr) => {
        if (Object.prototype.hasOwnProperty.call(cr, "operand")) {
            return filter.has_operand(cr.operator, cr.operand);
        }
        return filter.has_operator(cr.operator);
    });
}

function check_validity(last, operators, valid, invalid) {
    // valid: list of strings valid for the last operator
    // invalid: list of operators invalid for any previous operators except last.
    if (!valid.includes(last.operator)) {
        return false;
    }
    if (match_criteria(operators, invalid)) {
        return false;
    }
    return true;
}

function format_as_suggestion(terms) {
    return {
        description: Filter.describe(terms),
        search_string: Filter.unparse(terms),
    };
}

function compare_by_huddle(huddle) {
    huddle = huddle.slice(0, -1).map((person) => {
        person = people.get_by_email(person);
        return person && person.user_id;
    });

    // Construct dict for all huddles, so we can lookup each's recency
    const huddles = huddle_data.get_huddles();
    const huddle_dict = new Map();
    for (const [i, huddle] of huddles.entries()) {
        huddle_dict.set(huddle, i + 1);
    }

    return function (person1, person2) {
        const huddle1 = people.concat_huddle(huddle, person1.user_id);
        const huddle2 = people.concat_huddle(huddle, person2.user_id);

        // If not in the dict, assign an arbitrarily high index
        const score1 = huddle_dict.get(huddle1) || huddles.length + 1;
        const score2 = huddle_dict.get(huddle2) || huddles.length + 1;
        const diff = score1 - score2;

        if (diff !== 0) {
            return diff;
        }
        return typeahead_helper.compare_by_pms(person1, person2);
    };
}

function get_stream_suggestions(last, operators) {
    const valid = ["stream", "search", ""];
    const invalid = [
        {operator: "stream"},
        {operator: "streams"},
        {operator: "is", operand: "private"},
        {operator: "pm-with"},
    ];
    if (!check_validity(last, operators, valid, invalid)) {
        return [];
    }

    const query = last.operand;
    let streams = stream_data.subscribed_streams();

    streams = streams.filter((stream) => stream_matches_query(stream, query));

    streams = typeahead_helper.sorter(query, streams);

    const regex = typeahead_helper.build_highlight_regex(query);
    const hilite = typeahead_helper.highlight_with_escaping_and_regex;

    const objs = streams.map((stream) => {
        const prefix = "stream";
        const highlighted_stream = hilite(regex, stream);
        const verb = last.negated ? "exclude " : "";
        const description = verb + prefix + " " + highlighted_stream;
        const term = {
            operator: "stream",
            operand: stream,
            negated: last.negated,
        };
        const search_string = Filter.unparse([term]);
        return {description, search_string};
    });

    return objs;
}

function get_group_suggestions(last, operators) {
    if (!check_validity(last, operators, ["pm-with"], [{operator: "stream"}])) {
        return [];
    }

    const operand = last.operand;
    const negated = last.negated;

    // The operand has the form "part1,part2,pa", where all but the last part
    // are emails, and the last part is an arbitrary query.
    //
    // We only generate group suggestions when there's more than one part, and
    // we only use the last part to generate suggestions.

    const last_comma_index = operand.lastIndexOf(",");
    if (last_comma_index < 0) {
        return [];
    }

    // Neither all_but_last_part nor last_part include the final comma.
    const all_but_last_part = operand.slice(0, last_comma_index);
    const last_part = operand.slice(last_comma_index + 1);

    // We don't suggest a person if their email is already present in the
    // operand (not including the last part).
    const parts = all_but_last_part.split(",").concat(people.my_current_email());

    const person_matcher = people.build_person_matcher(last_part);
    let persons = people.filter_all_persons((person) => {
        if (parts.includes(person.email)) {
            return false;
        }
        return last_part === "" || person_matcher(person);
    });

    persons.sort(compare_by_huddle(parts));

    // Take top 15 persons, since they're ordered by pm_recipient_count.
    persons = persons.slice(0, 15);

    const prefix = Filter.operator_to_prefix("pm-with", negated);

    const highlight_person = make_person_highlighter(last_part);

    const suggestions = persons.map((person) => {
        const term = {
            operator: "pm-with",
            operand: all_but_last_part + "," + person.email,
            negated,
        };
        const name = highlight_person(person);
        const description =
            prefix + " " + Handlebars.Utils.escapeExpression(all_but_last_part) + "," + name;
        let terms = [term];
        if (negated) {
            terms = [{operator: "is", operand: "private"}, term];
        }
        const search_string = Filter.unparse(terms);
        return {description, search_string};
    });

    return suggestions;
}

function make_people_getter(last) {
    let persons;

    /* The next function will be called between 0 and 4
       times for each keystroke in a search, but we will
       only do real work one time.
    */
    return function () {
        if (persons !== undefined) {
            return persons;
        }

        let query;

        // This next block is designed to match the behavior of the
        // `is:private` block in get_person_suggestions
        if (last.operator === "is" && last.operand === "private") {
            query = "";
        } else {
            query = last.operand;
        }

        persons = people.get_people_for_search_bar(query);
        persons.sort(typeahead_helper.compare_by_pms);
        return persons;
    };
}

// Possible args for autocomplete_operator: pm-with, sender, from
function get_person_suggestions(people_getter, last, operators, autocomplete_operator) {
    if (last.operator === "is" && last.operand === "private") {
        // Interpret 'is:private' as equivalent to 'pm-with:'
        last = {operator: "pm-with", operand: "", negated: false};
    }

    const query = last.operand;

    // Be especially strict about the less common "from" operator.
    if (autocomplete_operator === "from" && last.operator !== "from") {
        return [];
    }

    const valid = ["search", autocomplete_operator];
    let invalid;
    if (autocomplete_operator === "pm-with") {
        invalid = [{operator: "pm-with"}, {operator: "stream"}];
    } else {
        // If not pm-with, then this must either be 'sender' or 'from'
        invalid = [{operator: "sender"}, {operator: "from"}];
    }

    if (!check_validity(last, operators, valid, invalid)) {
        return [];
    }

    const persons = people_getter();

    const prefix = Filter.operator_to_prefix(autocomplete_operator, last.negated);

    const highlight_person = make_person_highlighter(query);

    const objs = persons.map((person) => {
        const name = highlight_person(person);
        const description = prefix + " " + name;
        const terms = [
            {
                operator: autocomplete_operator,
                operand: person.email,
                negated: last.negated,
            },
        ];
        if (autocomplete_operator === "pm-with" && last.negated) {
            // In the special case of '-pm-with', add 'is:private' before it
            // because we assume the user still wants to narrow to PMs
            terms.unshift({operator: "is", operand: "private"});
        }
        const search_string = Filter.unparse(terms);
        return {description, search_string};
    });

    return objs;
}

function get_default_suggestion(operators) {
    // Here we return the canonical suggestion for the query that the
    // user typed. (The caller passes us the parsed query as "operators".)
    if (operators.length === 0) {
        return {description: "", search_string: ""};
    }
    return format_as_suggestion(operators);
}

function get_topic_suggestions(last, operators) {
    const invalid = [
        {operator: "pm-with"},
        {operator: "is", operand: "private"},
        {operator: "topic"},
    ];
    if (!check_validity(last, operators, ["stream", "topic", "search"], invalid)) {
        return [];
    }

    const operator = Filter.canonicalize_operator(last.operator);
    const operand = last.operand;
    const negated = operator === "topic" && last.negated;
    let stream;
    let guess;
    const filter = new Filter(operators);
    const suggest_operators = [];

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
        case "stream":
            guess = "";
            stream = operand;
            suggest_operators.push(last);
            break;
        case "topic":
        case "search":
            guess = operand;
            if (filter.has_operator("stream")) {
                stream = filter.operands("stream")[0];
            } else {
                stream = narrow_state.stream();
                suggest_operators.push({operator: "stream", operand: stream});
            }
            break;
    }

    if (!stream) {
        return [];
    }

    const stream_id = stream_data.get_stream_id(stream);
    if (!stream_id) {
        return [];
    }

    let topics = stream_topic_history.get_recent_topic_names(stream_id);

    if (!topics || !topics.length) {
        return [];
    }

    // Be defensive here in case stream_data.get_recent_topics gets
    // super huge, but still slice off enough topics to find matches.
    topics = topics.slice(0, 300);

    if (guess !== "") {
        topics = topics.filter((topic) => common.phrase_match(guess, topic));
    }

    topics = topics.slice(0, 10);

    // Just use alphabetical order.  While recency and read/unreadness of
    // topics do matter in some contexts, you can get that from the left sidebar,
    // and I'm leaning toward high scannability for autocompletion.  I also don't
    // care about case.
    topics.sort();

    return topics.map((topic) => {
        const topic_term = {operator: "topic", operand: topic, negated};
        const operators = suggest_operators.concat([topic_term]);
        return format_as_suggestion(operators);
    });
}

function get_operator_subset_suggestions(operators) {
    // For stream:a topic:b search:c, suggest:
    //  stream:a topic:b
    //  stream:a
    if (operators.length < 1) {
        return [];
    }

    let i;
    const suggestions = [];

    for (i = operators.length - 1; i >= 1; i -= 1) {
        const subset = operators.slice(0, i);
        suggestions.push(format_as_suggestion(subset));
    }

    return suggestions;
}

function get_special_filter_suggestions(last, operators, suggestions) {
    const is_search_operand_negated = last.operator === "search" && last.operand[0] === "-";
    // Negating suggestions on is_search_operand_negated is required for
    // suggesting negated operators.
    if (last.negated || is_search_operand_negated) {
        suggestions = suggestions.map((suggestion) => ({
            search_string: "-" + suggestion.search_string,
            description: "exclude " + suggestion.description,
            invalid: suggestion.invalid,
        }));
    }

    const last_string = Filter.unparse([last]).toLowerCase();
    suggestions = suggestions.filter((s) => {
        if (match_criteria(operators, s.invalid)) {
            return false;
        }
        if (last_string === "") {
            return true;
        }

        // returns the substring after the ":" symbol.
        const suggestion_operand = s.search_string.substring(s.search_string.indexOf(":") + 1);
        // e.g for `att` search query, `has:attachment` should be suggested.
        const show_operator_suggestions =
            last.operator === "search" && suggestion_operand.toLowerCase().startsWith(last_string);
        return (
            s.search_string.toLowerCase().startsWith(last_string) ||
            show_operator_suggestions ||
            s.description.toLowerCase().startsWith(last_string)
        );
    });

    // Only show home if there's an empty bar
    if (operators.length === 0 && last_string === "") {
        suggestions.unshift({search_string: "", description: "All messages"});
    }
    return suggestions;
}

function get_streams_filter_suggestions(last, operators) {
    const suggestions = [
        {
            search_string: "streams:public",
            description: "All public streams in organization",
            invalid: [
                {operator: "is", operand: "private"},
                {operator: "stream"},
                {operator: "group-pm-with"},
                {operator: "pm-with"},
                {operator: "in"},
                {operator: "streams"},
            ],
        },
    ];
    return get_special_filter_suggestions(last, operators, suggestions);
}
function get_is_filter_suggestions(last, operators) {
    const suggestions = [
        {
            search_string: "is:private",
            description: "private messages",
            invalid: [
                {operator: "is", operand: "private"},
                {operator: "stream"},
                {operator: "pm-with"},
                {operator: "in"},
            ],
        },
        {
            search_string: "is:starred",
            description: "starred messages",
            invalid: [{operator: "is", operand: "starred"}],
        },
        {
            search_string: "is:mentioned",
            description: "@-mentions",
            invalid: [{operator: "is", operand: "mentioned"}],
        },
        {
            search_string: "is:alerted",
            description: "alerted messages",
            invalid: [{operator: "is", operand: "alerted"}],
        },
        {
            search_string: "is:unread",
            description: "unread messages",
            invalid: [{operator: "is", operand: "unread"}],
        },
    ];
    return get_special_filter_suggestions(last, operators, suggestions);
}

function get_has_filter_suggestions(last, operators) {
    const suggestions = [
        {
            search_string: "has:link",
            description: "messages with one or more link",
            invalid: [{operator: "has", operand: "link"}],
        },
        {
            search_string: "has:image",
            description: "messages with one or more image",
            invalid: [{operator: "has", operand: "image"}],
        },
        {
            search_string: "has:attachment",
            description: "messages with one or more attachment",
            invalid: [{operator: "has", operand: "attachment"}],
        },
    ];
    return get_special_filter_suggestions(last, operators, suggestions);
}

function get_sent_by_me_suggestions(last, operators) {
    const last_string = Filter.unparse([last]).toLowerCase();
    const negated = last.negated || (last.operator === "search" && last.operand[0] === "-");
    const negated_symbol = negated ? "-" : "";
    const verb = negated ? "exclude " : "";

    const sender_query = negated_symbol + "sender:" + people.my_current_email();
    const from_query = negated_symbol + "from:" + people.my_current_email();
    const sender_me_query = negated_symbol + "sender:me";
    const from_me_query = negated_symbol + "from:me";
    const sent_string = negated_symbol + "sent";
    const description = verb + "sent by me";

    const invalid = [{operator: "sender"}, {operator: "from"}];

    if (match_criteria(operators, invalid)) {
        return [];
    }

    if (
        last.operator === "" ||
        sender_query.startsWith(last_string) ||
        sender_me_query.startsWith(last_string) ||
        last_string === sent_string
    ) {
        return [
            {
                search_string: sender_query,
                description,
            },
        ];
    } else if (from_query.startsWith(last_string) || from_me_query.startsWith(last_string)) {
        return [
            {
                search_string: from_query,
                description,
            },
        ];
    }
    return [];
}

function get_operator_suggestions(last) {
    if (!(last.operator === "search")) {
        return [];
    }
    let last_operand = last.operand;

    let negated = false;
    if (last_operand.startsWith("-")) {
        negated = true;
        last_operand = last_operand.slice(1);
    }

    let choices = ["stream", "topic", "pm-with", "sender", "near", "from", "group-pm-with"];
    choices = choices.filter((choice) => common.phrase_match(last_operand, choice));

    return choices.map((choice) => {
        const op = [{operator: choice, operand: "", negated}];
        return format_as_suggestion(op);
    });
}

class Attacher {
    result = [];
    prev = new Set();

    constructor(base) {
        this.base = base;
    }

    prepend_base(suggestion) {
        if (this.base && this.base.description.length > 0) {
            suggestion.search_string = this.base.search_string + " " + suggestion.search_string;
            suggestion.description = this.base.description + ", " + suggestion.description;
        }
    }

    push(suggestion) {
        if (!this.prev.has(suggestion.search_string)) {
            this.prev.add(suggestion.search_string);
            this.result.push(suggestion);
        }
    }

    concat(suggestions) {
        for (const suggestion of suggestions) {
            this.push(suggestion);
        }
    }

    attach_many(suggestions) {
        for (const suggestion of suggestions) {
            this.prepend_base(suggestion);
            this.push(suggestion);
        }
    }
}

exports.get_search_result = function (base_query, query) {
    let suggestion;
    let all_operators;

    // search_operators correspond to the operators for the query in the input.
    // For search_pills_enabled, this includes just editable query where search pills
    // have not been created yet.
    // And for this disabled case, this includes the entire query entered in the searchbox.
    // operators correspond to the operators for the entire query entered in the searchbox.
    if (page_params.search_pills_enabled) {
        all_operators = Filter.parse((base_query + " " + query).trim());
    }
    const search_operators = Filter.parse(query);
    let last = {operator: "", operand: "", negated: false};
    if (search_operators.length > 0) {
        last = search_operators.slice(-1)[0];
    } else if (page_params.search_pills_enabled) {
        // We push an empty term so that we can get suggestions
        // on the empty string based on the base query which is
        // calculated from the created search pills.
        // Else search results are returned as if the user is still
        // typing the non-editable last search pill.
        all_operators.push(last);
        search_operators.push(last);
    }

    const person_suggestion_ops = ["sender", "pm-with", "from", "group-pm"];
    const search_operators_len = search_operators.length;

    // Handle spaces in person name in new suggestions only. Checks if the last operator is 'search'
    // and the second last operator in search_operators is one out of person_suggestion_ops.
    // e.g for `sender:Ted sm`, initially last = {operator: 'search', operand: 'sm'....}
    // and second last is {operator: 'sender', operand: 'sm'....}. If the second last operand
    // is an email of a user, both of these operators remain unchanged. Otherwise search operator
    // will be deleted and new last will become {operator:'sender', operand: 'Ted sm`....}.
    if (
        search_operators_len > 1 &&
        last.operator === "search" &&
        person_suggestion_ops.includes(search_operators[search_operators_len - 2].operator)
    ) {
        const person_op = search_operators[search_operators_len - 2];
        if (!people.reply_to_to_user_ids_string(person_op.operand)) {
            last = {
                operator: person_op.operator,
                operand: person_op.operand + " " + last.operand,
                negated: person_op.negated,
            };
            if (page_params.search_pills_enabled) {
                all_operators[all_operators.length - 2] = last;
                all_operators.splice(-1, 1);
            }
            search_operators[search_operators_len - 2] = last;
            search_operators.splice(-1, 1);
        }
    }

    const base = get_default_suggestion(search_operators.slice(0, -1));
    const attacher = new Attacher(base);

    // Display the default first
    // `has` and `is` operators work only on predefined categories. Default suggestion
    // is not displayed in that case. e.g. `messages with one or more abc` as
    // a suggestion for `has:abc`does not make sense.
    if (last.operator !== "" && last.operator !== "has" && last.operator !== "is") {
        suggestion = get_default_suggestion(search_operators);
        attacher.push(suggestion);
    }

    // only make one people_getter to avoid duplicate work
    const people_getter = make_people_getter(last);

    function get_people(flavor) {
        return function (last, base_operators) {
            return get_person_suggestions(people_getter, last, base_operators, flavor);
        };
    }

    const filterers = [
        get_streams_filter_suggestions,
        get_is_filter_suggestions,
        get_sent_by_me_suggestions,
        get_stream_suggestions,
        get_people("sender"),
        get_people("pm-with"),
        get_people("from"),
        get_people("group-pm-with"),
        get_group_suggestions,
        get_topic_suggestions,
        get_operator_suggestions,
        get_has_filter_suggestions,
    ];

    if (!page_params.search_pills_enabled) {
        all_operators = search_operators;
    }
    const base_operators = all_operators.slice(0, -1);
    const max_items = exports.max_num_of_search_results;

    for (const filterer of filterers) {
        if (attacher.result.length < max_items) {
            const suggestions = filterer(last, base_operators);
            attacher.attach_many(suggestions);
        }
    }

    if (!page_params.search_pills_enabled) {
        // This is unique to the legacy search system.  With pills
        // it is difficult to "suggest" a subset of operators,
        // and there's a more natural mechanism under that paradigm,
        // where the user just deletes one or more pills.  So you
        // won't see this is in the new code.
        if (attacher.result.length < max_items) {
            const subset_suggestions = get_operator_subset_suggestions(search_operators);
            attacher.concat(subset_suggestions);
        }
    }

    return attacher.result.slice(0, max_items);
};

exports.get_suggestions = function (base_query, query) {
    const result = exports.get_search_result(base_query, query);
    return exports.finalize_search_result(result);
};

exports.finalize_search_result = function (result) {
    for (const sug of result) {
        const first = sug.description.charAt(0).toUpperCase();
        sug.description = first + sug.description.slice(1);
    }

    // Typeahead expects us to give it strings, not objects,
    // so we maintain our own hash back to our objects
    const lookup_table = new Map();

    for (const obj of result) {
        lookup_table.set(obj.search_string, obj);
    }

    const strings = result.map((obj) => obj.search_string);
    return {
        strings,
        lookup_table,
    };
};

window.search_suggestion = exports;
