import Handlebars from "handlebars/runtime";

import * as common from "./common";
import {Filter} from "./filter";
import * as huddle_data from "./huddle_data";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as stream_data from "./stream_data";
import * as stream_topic_history from "./stream_topic_history";
import * as stream_topic_history_util from "./stream_topic_history_util";
import * as typeahead_helper from "./typeahead_helper";

export const max_num_of_search_results = 12;

function stream_matches_query(stream_name, q) {
    return common.phrase_match(q, stream_name);
}

function make_person_highlighter(query) {
    const highlight_query = typeahead_helper.make_query_highlighter(query);

    return function (person) {
        return highlight_query(person.full_name);
    };
}

function highlight_person(person, highlighter) {
    const avatar_url = people.small_avatar_url_for_person(person);
    const highlighted_name = highlighter(person);

    return {
        id: person.user_id,
        display_value: new Handlebars.SafeString(highlighted_name),
        has_image: true,
        img_src: avatar_url,
    };
}

function match_criteria(operators, criteria) {
    const filter = new Filter(operators);
    return criteria.some((cr) => {
        if (Object.hasOwn(cr, "operand")) {
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
        description_html: Filter.search_description_as_html(terms),
        search_string: Filter.unparse(terms),
    };
}

function compare_by_huddle(huddle) {
    huddle = huddle.slice(0, -1).map((person) => {
        person = people.get_by_email(person);
        return person && person.user_id;
    });

    // Construct dict for all huddles, so we can look up each's recency
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
        {operator: "is", operand: "dm"},
        {operator: "dm"},
        {operator: "dm-including"},
    ];
    if (!check_validity(last, operators, valid, invalid)) {
        return [];
    }

    const query = last.operand;
    let streams = stream_data.subscribed_streams();

    streams = streams.filter((stream) => stream_matches_query(stream, query));

    streams = typeahead_helper.sorter(query, streams, (x) => x);

    const regex = typeahead_helper.build_highlight_regex(query);
    const highlight_query = typeahead_helper.highlight_with_escaping_and_regex;

    const objs = streams.map((stream) => {
        const prefix = "stream";
        const highlighted_stream = highlight_query(regex, stream);
        const verb = last.negated ? "exclude " : "";
        const description_html = verb + prefix + " " + highlighted_stream;
        const term = {
            operator: "stream",
            operand: stream,
            negated: last.negated,
        };
        const search_string = Filter.unparse([term]);
        return {description_html, search_string};
    });

    return objs;
}

function get_group_suggestions(last, operators) {
    // For users with "pm-with" in their muscle memory, still
    // have group direct message suggestions with "dm:" operator.
    if (!check_validity(last, operators, ["dm", "pm-with"], [{operator: "stream"}])) {
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
    const parts = [...all_but_last_part.split(","), people.my_current_email()];

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

    const prefix = Filter.operator_to_prefix("dm", negated);

    const person_highlighter = make_person_highlighter(last_part);

    const suggestions = persons.map((person) => {
        const term = {
            operator: "dm",
            operand: all_but_last_part + "," + person.email,
            negated,
        };

        // Note that description_html won't contain the user's
        // identity; that instead will be rendered in the separate
        // user pill.
        const description_html =
            prefix + Handlebars.Utils.escapeExpression(" " + all_but_last_part + ",");

        let terms = [term];
        if (negated) {
            terms = [{operator: "is", operand: "dm"}, term];
        }

        return {
            description_html,
            search_string: Filter.unparse(terms),
            is_person: true,
            user_pill_context: highlight_person(person, person_highlighter),
        };
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

        // This next block is designed to match the behavior
        // of the "is:dm" block in get_person_suggestions.
        if (last.operator === "is" && last.operand === "dm") {
            query = "";
        } else {
            query = last.operand;
        }

        persons = people.get_people_for_search_bar(query);
        persons.sort(typeahead_helper.compare_by_pms);
        return persons;
    };
}

// Possible args for autocomplete_operator: dm, pm-with, sender, from, dm-including
function get_person_suggestions(people_getter, last, operators, autocomplete_operator) {
    if ((last.operator === "is" && last.operand === "dm") || last.operator === "pm-with") {
        // Interpret "is:dm" or "pm-with:" operator as equivalent to "dm:".
        last = {operator: "dm", operand: "", negated: false};
    }

    const query = last.operand;

    // Be especially strict about the less common "from" operator.
    if (autocomplete_operator === "from" && last.operator !== "from") {
        return [];
    }

    const valid = ["search", autocomplete_operator];
    let invalid;

    switch (autocomplete_operator) {
        case "dm-including":
            invalid = [{operator: "stream"}, {operator: "is", operand: "resolved"}];
            break;
        case "dm":
        case "pm-with":
            invalid = [
                {operator: "dm"},
                {operator: "pm-with"},
                {operator: "stream"},
                {operator: "is", operand: "resolved"},
            ];
            break;
        case "sender":
        case "from":
            invalid = [{operator: "sender"}, {operator: "from"}];
            break;
    }

    if (!check_validity(last, operators, valid, invalid)) {
        return [];
    }

    const persons = people_getter();

    const prefix = Filter.operator_to_prefix(autocomplete_operator, last.negated);

    const person_highlighter = make_person_highlighter(query);

    const objs = persons.map((person) => {
        const terms = [
            {
                operator: autocomplete_operator,
                operand: person.email,
                negated: last.negated,
            },
        ];

        if (
            last.negated &&
            (autocomplete_operator === "dm" || autocomplete_operator === "pm-with")
        ) {
            // In the special case of "-dm" or "-pm-with", add "is:dm" before
            // it because we assume the user still wants to narrow to direct
            // messages.
            terms.unshift({operator: "is", operand: "dm"});
        }

        return {
            description_html: prefix,
            search_string: Filter.unparse(terms),
            is_person: true,
            user_pill_context: highlight_person(person, person_highlighter),
        };
    });

    return objs;
}

function get_default_suggestion(operators) {
    // Here we return the canonical suggestion for the query that the
    // user typed. (The caller passes us the parsed query as "operators".)
    if (operators.length === 0) {
        return {description_html: "", search_string: ""};
    }
    return format_as_suggestion(operators);
}

export function get_topic_suggestions_from_candidates({candidate_topics, guess}) {
    // This function is exported for unit testing purposes.
    const max_num_topics = 10;

    if (guess === "") {
        // In the search UI, once you autocomplete the stream,
        // we just show you the most recent topics before you even
        // need to start typing any characters.
        return candidate_topics.slice(0, max_num_topics);
    }

    // Once the user starts typing characters for a topic name,
    // it is pretty likely they want to get suggestions for
    // topics that may be fairly low in our list of candidates,
    // so we do an aggressive search here.
    //
    // The following loop can be expensive if you have lots
    // of topics in a stream, so we try to exit the loop as
    // soon as we find enough matches.
    const topics = [];
    for (const topic of candidate_topics) {
        if (common.phrase_match(guess, topic)) {
            topics.push(topic);
            if (topics.length >= max_num_topics) {
                break;
            }
        }
    }

    return topics;
}

function get_topic_suggestions(last, operators) {
    const invalid = [
        {operator: "dm"},
        {operator: "is", operand: "dm"},
        {operator: "dm-including"},
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
                stream = narrow_state.stream_name();
                suggest_operators.push({operator: "stream", operand: stream});
            }
            break;
    }

    if (!stream) {
        return [];
    }

    const stream_sub = stream_data.get_sub(stream);
    if (!stream_sub) {
        return [];
    }

    if (stream_data.can_access_topic_history(stream_sub)) {
        // Fetch topic history from the server, in case we will need it.
        // Note that we won't actually use the results from the server here
        // for this particular keystroke from the user, because we want to
        // show results immediately. Assuming the server responds quickly,
        // as the user makes their search more specific, subsequent calls to
        // this function will get more candidates from calling
        // stream_topic_history.get_recent_topic_names.
        stream_topic_history_util.get_server_history(stream_sub.stream_id, () => {});
    }

    const candidate_topics = stream_topic_history.get_recent_topic_names(stream_sub.stream_id);

    if (!candidate_topics || !candidate_topics.length) {
        return [];
    }

    const topics = get_topic_suggestions_from_candidates({candidate_topics, guess});

    // Just use alphabetical order.  While recency and read/unreadness of
    // topics do matter in some contexts, you can get that from the left sidebar,
    // and I'm leaning toward high scannability for autocompletion.  I also don't
    // care about case.
    topics.sort();

    return topics.map((topic) => {
        const topic_term = {operator: "topic", operand: topic, negated};
        const operators = [...suggest_operators, topic_term];
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
            description_html: "exclude " + suggestion.description_html,
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
        const suggestion_operand = s.search_string.slice(s.search_string.indexOf(":") + 1);
        // e.g for `att` search query, `has:attachment` should be suggested.
        const show_operator_suggestions =
            last.operator === "search" && suggestion_operand.toLowerCase().startsWith(last_string);
        return (
            s.search_string.toLowerCase().startsWith(last_string) ||
            show_operator_suggestions ||
            s.description_html.toLowerCase().startsWith(last_string)
        );
    });

    // Only show home if there's an empty bar
    if (operators.length === 0 && last_string === "") {
        suggestions.unshift({search_string: "", description_html: "All messages"});
    }
    return suggestions;
}

function get_streams_filter_suggestions(last, operators) {
    const suggestions = [
        {
            search_string: "streams:public",
            description_html: "All public streams in organization",
            invalid: [
                {operator: "is", operand: "dm"},
                {operator: "stream"},
                {operator: "dm-including"},
                {operator: "dm"},
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
            search_string: "is:dm",
            description_html: "direct messages",
            invalid: [
                {operator: "is", operand: "dm"},
                {operator: "is", operand: "resolved"},
                {operator: "stream"},
                {operator: "dm"},
                {operator: "in"},
            ],
        },
        {
            search_string: "is:starred",
            description_html: "starred messages",
            invalid: [{operator: "is", operand: "starred"}],
        },
        {
            search_string: "is:mentioned",
            description_html: "@-mentions",
            invalid: [{operator: "is", operand: "mentioned"}],
        },
        {
            search_string: "is:alerted",
            description_html: "alerted messages",
            invalid: [{operator: "is", operand: "alerted"}],
        },
        {
            search_string: "is:unread",
            description_html: "unread messages",
            invalid: [{operator: "is", operand: "unread"}],
        },
        {
            search_string: "is:resolved",
            description_html: "topics marked as resolved",
            invalid: [
                {operator: "is", operand: "resolved"},
                {operator: "is", operand: "dm"},
                {operator: "dm"},
                {operator: "dm-including"},
            ],
        },
    ];
    return get_special_filter_suggestions(last, operators, suggestions);
}

function get_has_filter_suggestions(last, operators) {
    const suggestions = [
        {
            search_string: "has:link",
            description_html: "messages that contain links",
            invalid: [{operator: "has", operand: "link"}],
        },
        {
            search_string: "has:image",
            description_html: "messages that contain images",
            invalid: [{operator: "has", operand: "image"}],
        },
        {
            search_string: "has:attachment",
            description_html: "messages that contain attachments",
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
    const description_html = verb + "sent by me";

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
                description_html,
            },
        ];
    } else if (from_query.startsWith(last_string) || from_me_query.startsWith(last_string)) {
        return [
            {
                search_string: from_query,
                description_html,
            },
        ];
    }
    return [];
}

function get_operator_suggestions(last) {
    // Suggest "is:dm" to anyone with "is:private" in their muscle memory
    if (last.operator === "is" && common.phrase_match(last.operand, "private")) {
        const is_dm = format_as_suggestion([
            {operator: last.operator, operand: "dm", negated: last.negated},
        ]);
        return [is_dm];
    }

    if (!(last.operator === "search")) {
        return [];
    }
    let last_operand = last.operand;

    let negated = false;
    if (last_operand.startsWith("-")) {
        negated = true;
        last_operand = last_operand.slice(1);
    }

    let choices = ["stream", "topic", "dm", "dm-including", "sender", "near", "from", "pm-with"];
    choices = choices.filter((choice) => common.phrase_match(last_operand, choice));

    return choices.map((choice) => {
        // Map results for "dm:" operator for users
        // who have "pm-with" in their muscle memory.
        if (choice === "pm-with") {
            choice = "dm";
        }
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
        if (this.base && this.base.description_html.length > 0) {
            suggestion.search_string = this.base.search_string + " " + suggestion.search_string;
            suggestion.description_html =
                this.base.description_html + ", " + suggestion.description_html;
        }
    }

    push(suggestion) {
        if (!this.prev.has(suggestion.search_string)) {
            this.prev.add(suggestion.search_string);
            this.result.push(suggestion);
        }
    }

    push_many(suggestions) {
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

export function get_search_result(query) {
    let suggestion;

    // search_operators correspond to the operators for the query in the input.
    // This includes the entire query entered in the searchbox.
    // operators correspond to the operators for the entire query entered in the searchbox.
    const search_operators = Filter.parse(query);
    let last = {operator: "", operand: "", negated: false};
    if (search_operators.length > 0) {
        last = search_operators.at(-1);
    }

    const person_suggestion_ops = ["sender", "dm", "dm-including", "from", "pm-with"];

    // Handle spaces in person name in new suggestions only. Checks if the last operator is 'search'
    // and the second last operator in search_operators is one out of person_suggestion_ops.
    // e.g for `sender:Ted sm`, initially last = {operator: 'search', operand: 'sm'....}
    // and second last is {operator: 'sender', operand: 'sm'....}. If the second last operand
    // is an email of a user, both of these operators remain unchanged. Otherwise search operator
    // will be deleted and new last will become {operator:'sender', operand: 'Ted sm`....}.
    if (
        search_operators.length > 1 &&
        last.operator === "search" &&
        person_suggestion_ops.includes(search_operators.at(-2).operator)
    ) {
        const person_op = search_operators.at(-2);
        if (!people.reply_to_to_user_ids_string(person_op.operand)) {
            last = {
                operator: person_op.operator,
                operand: person_op.operand + " " + last.operand,
                negated: person_op.negated,
            };
            search_operators.splice(-2);
            search_operators.push(last);
        }
    }

    const base = get_default_suggestion(search_operators.slice(0, -1));
    const attacher = new Attacher(base);

    // Display the default first
    // `has` and `is` operators work only on predefined categories. Default suggestion
    // is not displayed in that case. e.g. `messages that contain abc` as
    // a suggestion for `has:abc`does not make sense.
    if (last.operator === "search") {
        suggestion = {
            search_string: last.operand,
            description_html: `search for <strong>${Handlebars.Utils.escapeExpression(
                last.operand,
            )}</strong>`,
        };
        attacher.prepend_base(suggestion);
        attacher.push(suggestion);
    } else if (last.operator !== "" && last.operator !== "has" && last.operator !== "is") {
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

    // Remember to update the spectator list when changing this.
    let filterers = [
        get_streams_filter_suggestions,
        get_is_filter_suggestions,
        get_sent_by_me_suggestions,
        get_stream_suggestions,
        get_people("sender"),
        get_people("dm"),
        get_people("dm-including"),
        get_people("from"),
        get_group_suggestions,
        get_topic_suggestions,
        get_operator_suggestions,
        get_has_filter_suggestions,
    ];

    if (page_params.is_spectator) {
        filterers = [
            get_stream_suggestions,
            get_people("sender"),
            get_people("from"),
            get_topic_suggestions,
            get_operator_suggestions,
            get_has_filter_suggestions,
        ];
    }

    const base_operators = search_operators.slice(0, -1);
    const max_items = max_num_of_search_results;

    for (const filterer of filterers) {
        if (attacher.result.length < max_items) {
            const suggestions = filterer(last, base_operators);
            attacher.attach_many(suggestions);
        }
    }

    if (attacher.result.length < max_items) {
        const subset_suggestions = get_operator_subset_suggestions(search_operators);
        attacher.push_many(subset_suggestions);
    }

    return attacher.result.slice(0, max_items);
}

export function get_suggestions(query) {
    const result = get_search_result(query);
    return finalize_search_result(result);
}

export function finalize_search_result(result) {
    for (const sug of result) {
        const first = sug.description_html.charAt(0).toUpperCase();
        sug.description_html = first + sug.description_html.slice(1);
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
}
