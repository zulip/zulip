import Handlebars from "handlebars/runtime.js";
import assert from "minimalistic-assert";

import {MAX_ITEMS} from "./bootstrap_typeahead.ts";
import * as common from "./common.ts";
import * as direct_message_group_data from "./direct_message_group_data.ts";
import {Filter} from "./filter.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import {type NarrowTerm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import * as util from "./util.ts";

export type UserPillItem = {
    id: number;
    display_value: string;
    has_image: boolean;
    img_src: string;
    should_add_guest_user_indicator: boolean;
};

type TermPattern = Omit<NarrowTerm, "operand"> & Partial<Pick<NarrowTerm, "operand">>;

export type Suggestion = {
    // When there's a single pill on a suggestion line, we have space to provide
    // help text (description_html) explaining what the operator does. If a
    // suggestion will be parsed into multiple pills, then we don't include
    // `description_html`.
    description_html: string | undefined;
    search_string: string;
};

export let max_num_of_search_results = MAX_ITEMS;
export function rewire_max_num_of_search_results(value: typeof max_num_of_search_results): void {
    max_num_of_search_results = value;
}

function channel_matches_query(channel_name: string, q: string): boolean {
    return common.phrase_match(q, channel_name);
}

function match_criteria(terms: NarrowTerm[], criteria: TermPattern[]): boolean {
    const filter = new Filter(terms);
    return criteria.some((cr) => {
        if (cr.operand !== undefined) {
            return filter.has_operand(cr.operator, cr.operand);
        }
        return filter.has_operator(cr.operator);
    });
}

function check_validity(
    last: NarrowTerm,
    terms: NarrowTerm[],
    valid: string[],
    incompatible_patterns: TermPattern[],
): boolean {
    // valid: list of strings valid for the last operator
    // incompatible_patterns: list of terms incompatible for any previous terms except last.
    if (!valid.includes(last.operator)) {
        return false;
    }
    if (match_criteria(terms, incompatible_patterns)) {
        return false;
    }
    return true;
}

function format_as_suggestion(terms: NarrowTerm[], is_operator_suggestion = false): Suggestion {
    return {
        description_html: Filter.search_description_as_html(terms, is_operator_suggestion),
        search_string: Filter.unparse(terms),
    };
}

function compare_by_direct_message_group(
    direct_message_group_emails: string[],
): (person1: User, person2: User) => number {
    const user_ids = direct_message_group_emails.slice(0, -1).flatMap((person) => {
        const user = people.get_by_email(person);
        return user?.user_id ?? [];
    });
    // Construct dict for all direct message groups, so we can
    // look up each's recency
    const direct_message_groups = direct_message_group_data.get_direct_message_groups();
    const direct_message_group_dict = new Map<string, number>();
    for (const [i, direct_message_group] of direct_message_groups.entries()) {
        direct_message_group_dict.set(direct_message_group, i + 1);
    }

    return function (person1: User, person2: User): number {
        const direct_message_group1 = people.concat_direct_message_group(user_ids, person1.user_id);
        const direct_message_group2 = people.concat_direct_message_group(user_ids, person2.user_id);
        // If not in the dict, assign an arbitrarily high index
        const score1 =
            direct_message_group_dict.get(direct_message_group1) ??
            direct_message_groups.length + 1;
        const score2 =
            direct_message_group_dict.get(direct_message_group2) ??
            direct_message_groups.length + 1;
        const diff = score1 - score2;

        if (diff !== 0) {
            return diff;
        }
        return typeahead_helper.compare_by_pms(person1, person2);
    };
}

function get_channel_suggestions(last: NarrowTerm, terms: NarrowTerm[]): Suggestion[] {
    // For users with "stream" in their muscle memory, still
    // have suggestions with "channel:" operator.
    const valid = ["stream", "channel", "search", ""];
    const incompatible_patterns = [
        {operator: "channel"},
        {operator: "channels"},
        {operator: "is", operand: "dm"},
        {operator: "dm"},
        {operator: "dm-including"},
    ];
    if (!check_validity(last, terms, valid, incompatible_patterns)) {
        return [];
    }

    const query = last.operand;
    let channels = stream_data.subscribed_streams();

    channels = channels.filter((channel_name) => channel_matches_query(channel_name, query));

    channels = typeahead_helper.sorter(query, channels, (x) => x);

    return channels.map((channel_name) => {
        const prefix = "messages in #";
        const verb = last.negated ? "exclude " : "";
        const description_html = verb + prefix + Handlebars.Utils.escapeExpression(channel_name);
        const channel = stream_data.get_sub_by_name(channel_name);
        assert(channel !== undefined);
        const term = {
            operator: "channel",
            operand: channel.stream_id.toString(),
            negated: last.negated,
        };
        const search_string = Filter.unparse([term]);
        return {description_html, search_string};
    });
}

function get_group_suggestions(last: NarrowTerm, terms: NarrowTerm[]): Suggestion[] {
    // We only suggest groups once a term with a valid user already exists
    if (terms.length === 0) {
        return [];
    }
    const last_complete_term = terms.at(-1)!;
    // For users with "pm-with" in their muscle memory, still
    // have group direct message suggestions with "dm:" operator.
    if (
        !check_validity(
            last_complete_term,
            terms.slice(-1),
            ["dm", "pm-with"],
            [{operator: "channel"}],
        )
    ) {
        return [];
    }

    // If they started typing since a user pill, we'll parse that as "search"
    // but they might actually want to parse that as a user instead to add to
    // the most recent pill. So we shuffle some things around to support that.
    if (last.operator === "search") {
        const text_input = last.operand;
        const operand = `${last_complete_term.operand},${text_input}`;
        last = {
            ...last_complete_term,
            operand,
        };
        terms = terms.slice(-1);
    } else if (last.operator === "") {
        last = last_complete_term;
    } else {
        // If they already started another term with an other operator, we're
        // no longer dealing with a group DM situation.
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
    let all_but_last_part;
    let last_part;
    if (last_comma_index === -1) {
        all_but_last_part = operand;
        last_part = "";
    } else {
        // Neither all_but_last_part nor last_part include the final comma.
        all_but_last_part = operand.slice(0, last_comma_index);
        last_part = operand.slice(last_comma_index + 1);
    }

    // We don't suggest a person if their email is already present in the
    // operand (not including the last part).
    const parts = [...all_but_last_part.split(","), people.my_current_email()];

    const all_users_but_last_part = [];
    for (const email of all_but_last_part.split(",")) {
        const user = people.get_by_email(email);
        // Somehow an invalid email is showing up earlier in the group.
        // This can happen if e.g. the user manually enters multiple emails.
        // We won't have group suggestions built from an invalid user, so
        // return an empty list.
        if (user === undefined) {
            return [];
        }
        all_users_but_last_part.push(user);
    }

    const person_matcher = people.build_person_matcher(last_part);
    let persons = people.filter_all_persons((person) => {
        if (parts.includes(person.email)) {
            return false;
        }
        return last_part === "" || person_matcher(person);
    });

    persons.sort(compare_by_direct_message_group(parts));

    // Take top 15 persons, since they're ordered by pm_recipient_count.
    persons = persons.slice(0, 15);

    const prefix = Filter.operator_to_prefix("dm", negated);

    return persons.map((person) => {
        const term = {
            operator: "dm",
            operand: all_but_last_part + "," + person.email,
            negated,
        };

        let terms: NarrowTerm[] = [term];
        if (negated) {
            terms = [{operator: "is", operand: "dm"}, term];
        }

        return {
            description_html: prefix,
            search_string: Filter.unparse(terms),
        };
    });
}

function make_people_getter(last: NarrowTerm): () => User[] {
    let persons: User[];

    /* The next function will be called between 0 and 4
       times for each keystroke in a search, but we will
       only do real work one time.
    */
    return function (): User[] {
        if (persons !== undefined) {
            return persons;
        }

        let query: string;

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
function get_person_suggestions(
    people_getter: () => User[],
    last: NarrowTerm,
    terms: NarrowTerm[],
    autocomplete_operator: string,
): Suggestion[] {
    if ((last.operator === "is" && last.operand === "dm") || last.operator === "pm-with") {
        // Interpret "is:dm" or "pm-with:" operator as equivalent to "dm:".
        last = {operator: "dm", operand: "", negated: false};
    }

    // Be especially strict about the less common "from" operator.
    if (autocomplete_operator === "from" && last.operator !== "from") {
        return [];
    }

    const valid = ["search", autocomplete_operator];
    let incompatible_patterns: TermPattern[] = [];

    switch (autocomplete_operator) {
        case "dm-including":
            incompatible_patterns = [{operator: "channel"}, {operator: "is", operand: "resolved"}];
            break;
        case "dm":
        case "pm-with":
            incompatible_patterns = [
                {operator: "dm"},
                {operator: "pm-with"},
                {operator: "channel"},
                {operator: "is", operand: "resolved"},
            ];
            break;
        case "sender":
        case "from":
            incompatible_patterns = [{operator: "sender"}, {operator: "from"}];
            break;
    }

    if (!check_validity(last, terms, valid, incompatible_patterns)) {
        return [];
    }

    const persons = people_getter();

    const prefix = Filter.operator_to_prefix(autocomplete_operator, last.negated);

    return persons.map((person) => {
        const terms: NarrowTerm[] = [
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
        };
    });
}

function get_default_suggestion_line(terms: NarrowTerm[]): SuggestionLine {
    if (terms.length === 0) {
        return [{description_html: "", search_string: ""}];
    }
    const suggestion_line = [];
    const suggestion_strings = new Set();
    for (const term of terms) {
        const suggestion = format_as_suggestion([term]);
        if (!suggestion_strings.has(suggestion.search_string)) {
            suggestion_line.push(suggestion);
            suggestion_strings.add(suggestion.search_string);
        }
    }
    return suggestion_line;
}

export function get_topic_suggestions_from_candidates({
    candidate_topics,
    guess,
}: {
    candidate_topics: string[];
    guess: string;
}): string[] {
    // This function is exported for unit testing purposes.
    const max_num_topics = 10;

    if (guess === "") {
        // In the search UI, once you autocomplete the channel,
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
    // of topics in a channel, so we try to exit the loop as
    // soon as we find enough matches.
    const topics: string[] = [];
    for (const topic of candidate_topics) {
        const topic_display_name = util.get_final_topic_display_name(topic);
        if (common.phrase_match(guess, topic_display_name)) {
            topics.push(topic);
            if (topics.length >= max_num_topics) {
                break;
            }
        }
    }

    return topics;
}

function get_topic_suggestions(last: NarrowTerm, terms: NarrowTerm[]): Suggestion[] {
    const incompatible_patterns = [
        {operator: "dm"},
        {operator: "is", operand: "dm"},
        {operator: "dm-including"},
        {operator: "topic"},
    ];
    if (!check_validity(last, terms, ["channel", "topic", "search"], incompatible_patterns)) {
        return [];
    }

    const operator = Filter.canonicalize_operator(last.operator);
    const operand = last.operand;
    const negated = operator === "topic" && last.negated;
    let channel_id: string | undefined;
    let guess: string | undefined;
    const filter = new Filter(terms);
    const suggest_terms: NarrowTerm[] = [];

    // channel:Rome -> show all Rome topics
    // channel:Rome topic: -> show all Rome topics
    // channel:Rome f -> show all Rome topics with a word starting in f
    // channel:Rome topic:f -> show all Rome topics with a word starting in f
    // channel:Rome topic:f -> show all Rome topics with a word starting in f

    // When narrowed to a channel:
    //   topic: -> show all topics in current channel
    //   foo -> show all topics in current channel with words starting with foo

    // If somebody explicitly types search:, then we might
    // not want to suggest topics, but I feel this is a very
    // minor issue, and Filter.parse() is currently lossy
    // in terms of telling us whether they provided the operator,
    // i.e. "foo" and "search:foo" both become [{operator: 'search', operand: 'foo'}].
    switch (operator) {
        case "channel":
            guess = "";
            channel_id = operand;
            suggest_terms.push(last);
            break;
        case "topic":
        case "search":
            guess = operand;
            if (filter.has_operator("channel")) {
                channel_id = filter.operands("channel")[0];
            } else {
                channel_id = narrow_state.stream_id()?.toString();
                if (channel_id) {
                    suggest_terms.push({operator: "channel", operand: channel_id});
                }
            }
            break;
    }

    if (!channel_id) {
        return [];
    }

    const subscription = stream_data.get_sub_by_id_string(channel_id);
    if (!subscription) {
        return [];
    }

    if (stream_data.can_access_topic_history(subscription)) {
        stream_topic_history_util.get_server_history(subscription.stream_id, () => {
            // Fetch topic history from the server, in case we will need it.
            // Note that we won't actually use the results from the server here
            // for this particular keystroke from the user, because we want to
            // show results immediately. Assuming the server responds quickly,
            // as the user makes their search more specific, subsequent calls to
            // this function will get more candidates from calling
            // stream_topic_history.get_recent_topic_names.
        });
    }

    const candidate_topics = stream_topic_history.get_recent_topic_names(subscription.stream_id);

    if (!candidate_topics?.length) {
        return [];
    }

    assert(guess !== undefined);
    const topics = get_topic_suggestions_from_candidates({candidate_topics, guess});

    // Just use alphabetical order.  While recency and read/unreadness of
    // topics do matter in some contexts, you can get that from the left sidebar,
    // and I'm leaning toward high scannability for autocompletion.  I also don't
    // care about case.
    topics.sort();

    return topics.map((topic) => {
        const topic_term = {operator: "topic", operand: topic, negated};
        const terms = [...suggest_terms, topic_term];
        return format_as_suggestion(terms);
    });
}

function get_term_subset_suggestions(terms: NarrowTerm[]): Suggestion[] {
    // For channel:a topic:b search:c, suggest:
    //  channel:a topic:b
    //  channel:a
    if (terms.length === 0) {
        return [];
    }

    const suggestions: Suggestion[] = [];

    for (let i = terms.length - 1; i >= 1; i -= 1) {
        const subset = terms.slice(0, i);
        suggestions.push(format_as_suggestion(subset));
    }

    return suggestions;
}

type SuggestionAndIncompatiblePatterns = Suggestion & {incompatible_patterns: TermPattern[]};

function get_special_filter_suggestions(
    last: NarrowTerm,
    terms: NarrowTerm[],
    suggestions: SuggestionAndIncompatiblePatterns[],
): Suggestion[] {
    const is_search_operand_negated = last.operator === "search" && last.operand.startsWith("-");
    // Negating suggestions on is_search_operand_negated is required for
    // suggesting negated terms.
    if (last.negated === true || is_search_operand_negated) {
        suggestions = suggestions
            .filter((suggestion) => suggestion.search_string !== "-is:resolved")
            .map((suggestion) => {
                // If the search_string is "is:resolved", we want to suggest "Unresolved topics"
                // instead of "Exclude resolved topics".
                if (suggestion.search_string === "is:resolved") {
                    return {
                        ...suggestion,
                        search_string: "-" + suggestion.search_string,
                        description_html: "unresolved topics",
                    };
                }
                return {
                    ...suggestion,
                    search_string: "-" + suggestion.search_string,
                    description_html: "exclude " + suggestion.description_html,
                };
            });
    }

    const last_string = Filter.unparse([last]).toLowerCase();
    suggestions = suggestions.filter((s) => {
        if (match_criteria(terms, s.incompatible_patterns)) {
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
            s.description_html?.toLowerCase().startsWith(last_string)
        );
    });
    const filtered_suggestions = suggestions.map(({incompatible_patterns, ...s}) => s);

    return filtered_suggestions;
}

function get_channels_filter_suggestions(last: NarrowTerm, terms: NarrowTerm[]): Suggestion[] {
    let search_string = "channels:public";
    // show "channels:public" option for users who
    // have "streams" in their muscle memory
    if (last.operator === "search" && common.phrase_match(last.operand, "streams")) {
        search_string = "streams:public";
    }
    let description_html = Filter.describe_public_channels(last.negated ?? false);
    description_html = description_html.charAt(0).toUpperCase() + description_html.slice(1);
    const suggestions: SuggestionAndIncompatiblePatterns[] = [
        {
            search_string,
            description_html,
            incompatible_patterns: [
                {operator: "is", operand: "dm"},
                {operator: "channel"},
                {operator: "dm-including"},
                {operator: "dm"},
                {operator: "in"},
                {operator: "channels"},
            ],
        },
    ];
    return get_special_filter_suggestions(last, terms, suggestions);
}
function get_is_filter_suggestions(last: NarrowTerm, terms: NarrowTerm[]): Suggestion[] {
    let suggestions: SuggestionAndIncompatiblePatterns[];
    if (page_params.is_spectator) {
        suggestions = [
            {
                search_string: "is:resolved",
                description_html: "resolved topics",
                incompatible_patterns: [
                    {operator: "is", operand: "resolved"},
                    {operator: "is", operand: "dm"},
                    {operator: "dm"},
                    {operator: "dm-including"},
                ],
            },
            {
                search_string: "-is:resolved",
                description_html: "unresolved topics",
                incompatible_patterns: [
                    {operator: "is", operand: "resolved"},
                    {operator: "is", operand: "dm"},
                    {operator: "dm"},
                    {operator: "dm-including"},
                ],
            },
        ];
    } else {
        suggestions = [
            {
                search_string: "is:dm",
                description_html: "direct messages",
                incompatible_patterns: [
                    {operator: "is", operand: "dm"},
                    {operator: "is", operand: "resolved"},
                    {operator: "channel"},
                    {operator: "dm"},
                    {operator: "in"},
                    {operator: "topic"},
                ],
            },
            {
                search_string: "is:starred",
                description_html: "starred messages",
                incompatible_patterns: [{operator: "is", operand: "starred"}],
            },
            {
                search_string: "is:mentioned",
                description_html: "messages that mention you",
                incompatible_patterns: [{operator: "is", operand: "mentioned"}],
            },
            {
                search_string: "is:followed",
                description_html: "followed topics",
                incompatible_patterns: [
                    {operator: "is", operand: "followed"},
                    {operator: "is", operand: "dm"},
                    {operator: "dm"},
                    {operator: "dm-including"},
                ],
            },
            {
                search_string: "is:alerted",
                description_html: "alerted messages",
                incompatible_patterns: [{operator: "is", operand: "alerted"}],
            },
            {
                search_string: "is:unread",
                description_html: "unread messages",
                incompatible_patterns: [{operator: "is", operand: "unread"}],
            },
            {
                search_string: "is:muted",
                description_html: "muted messages",
                incompatible_patterns: [
                    {operator: "is", operand: "muted"},
                    {operator: "in", operand: "home"},
                ],
            },
            {
                search_string: "is:resolved",
                description_html: "resolved topics",
                incompatible_patterns: [
                    {operator: "is", operand: "resolved"},
                    {operator: "is", operand: "dm"},
                    {operator: "dm"},
                    {operator: "dm-including"},
                ],
            },
            {
                search_string: "-is:resolved",
                description_html: "unresolved topics",
                incompatible_patterns: [
                    {operator: "is", operand: "resolved"},
                    {operator: "is", operand: "dm"},
                    {operator: "dm"},
                    {operator: "dm-including"},
                ],
            },
        ];
    }
    const special_filtered_suggestions = get_special_filter_suggestions(last, terms, suggestions);
    // Suggest "is:dm" to anyone with "is:private" in their muscle memory
    const other_suggestions = [];
    if (
        last.operator === "is" &&
        common.phrase_match(last.operand, "private") &&
        !page_params.is_spectator
    ) {
        const is_dm = format_as_suggestion([
            {operator: last.operator, operand: "dm", negated: last.negated},
        ]);
        other_suggestions.push(is_dm);
    }
    const all_suggestions = [...special_filtered_suggestions, ...other_suggestions];
    return all_suggestions;
}

function get_has_filter_suggestions(last: NarrowTerm, terms: NarrowTerm[]): Suggestion[] {
    const suggestions: SuggestionAndIncompatiblePatterns[] = [
        {
            search_string: "has:link",
            description_html: "messages with links",
            incompatible_patterns: [{operator: "has", operand: "link"}],
        },
        {
            search_string: "has:image",
            description_html: "messages with images",
            incompatible_patterns: [{operator: "has", operand: "image"}],
        },
        {
            search_string: "has:attachment",
            description_html: "messages with attachments",
            incompatible_patterns: [{operator: "has", operand: "attachment"}],
        },
        {
            search_string: "has:reaction",
            description_html: "messages with reactions",
            incompatible_patterns: [{operator: "has", operand: "reaction"}],
        },
    ];
    return get_special_filter_suggestions(last, terms, suggestions);
}

function get_sent_by_me_suggestions(last: NarrowTerm, terms: NarrowTerm[]): Suggestion[] {
    const last_string = Filter.unparse([last]).toLowerCase();
    const negated =
        last.negated === true || (last.operator === "search" && last.operand.startsWith("-"));
    const negated_symbol = negated ? "-" : "";
    const verb = negated ? "exclude " : "";

    const sender_query = negated_symbol + "sender:" + people.my_current_email();
    const sender_me_query = negated_symbol + "sender:me";
    const from_string = negated_symbol + "from";
    const sent_string = negated_symbol + "sent";
    const description_html = verb + "sent by me";

    const incompatible_patterns = [{operator: "sender"}, {operator: "from"}];

    if (match_criteria(terms, incompatible_patterns)) {
        return [];
    }

    if (
        last.operator === "" ||
        sender_query.startsWith(last_string) ||
        sender_me_query.startsWith(last_string) ||
        from_string.startsWith(last_string) ||
        last_string === sent_string
    ) {
        return [
            {
                search_string: sender_query,
                description_html,
            },
        ];
    }
    return [];
}

function get_operator_suggestions(last: NarrowTerm): Suggestion[] {
    if (!(last.operator === "search")) {
        return [];
    }
    let last_operand = last.operand;

    let negated = false;
    if (last_operand.startsWith("-")) {
        negated = true;
        last_operand = last_operand.slice(1);
    }

    let choices = [
        "channel",
        "topic",
        "dm",
        "dm-including",
        "sender",
        "near",
        "from",
        "pm-with",
        "stream",
    ];
    choices = choices.filter((choice) => common.phrase_match(last_operand, choice));

    return choices.map((choice) => {
        // Map results for "dm:" operator for users
        // who have "pm-with" in their muscle memory.
        if (choice === "pm-with") {
            choice = "dm";
        }
        // Map results for "channel:" operator for users
        // who have "stream" in their muscle memory.
        if (choice === "stream") {
            choice = "channel";
        }
        const op = [{operator: choice, operand: "", negated}];
        return format_as_suggestion(op, true);
    });
}

// One full search suggestion can include multiple search terms, based on what's
// in the search bar.
type SuggestionLine = Suggestion[];
function suggestion_search_string(suggestion_line: SuggestionLine): string {
    const search_strings = [];
    for (const suggestion of suggestion_line) {
        if (suggestion.search_string !== "") {
            // This is rendered as "Direct messages" and we want to make sure
            // that we don't add another suggestion for "is:dm" in parallel.
            if (suggestion.search_string === "is:private") {
                suggestion.search_string = "is:dm";
            }
            search_strings.push(suggestion.search_string);
        }
    }
    return search_strings.join(" ");
}

function suggestions_for_current_filter(): SuggestionLine[] {
    if (narrow_state.stream_id() && narrow_state.topic() !== undefined) {
        return [
            get_default_suggestion_line([
                {
                    operator: "channel",
                    operand: narrow_state.stream_id()!.toString(),
                },
            ]),
            get_default_suggestion_line(narrow_state.search_terms()),
        ];
    }
    if (narrow_state.pm_emails_string()) {
        return [
            get_default_suggestion_line([
                {
                    operator: "is",
                    operand: "dm",
                },
            ]),
            get_default_suggestion_line(narrow_state.search_terms()),
        ];
    }
    return [get_default_suggestion_line(narrow_state.search_terms())];
}

class Attacher {
    result: SuggestionLine[] = [];
    prev = new Set<string>();
    base: SuggestionLine;
    add_current_filter: boolean;

    constructor(base: SuggestionLine, search_query_is_empty: boolean, add_current_filter: boolean) {
        this.base = base;
        this.add_current_filter = add_current_filter;
        // Sometimes we add suggestions with the current filter in case
        // the user wants to search within the current filter. For an empty
        // search query, we put the current filter suggestions at the start
        // of the list.
        if (search_query_is_empty && this.add_current_filter) {
            this.add_current_filter = false;
            for (const current_filter_line of suggestions_for_current_filter()) {
                this.push(current_filter_line);
            }
        }
    }

    push(suggestion_line: SuggestionLine): void {
        const search_string = suggestion_search_string(suggestion_line);
        if (!this.prev.has(search_string.toLowerCase())) {
            this.prev.add(search_string.toLowerCase());
            this.result.push(suggestion_line);
        }
    }

    push_many(suggestion_lines: SuggestionLine[]): void {
        for (const line of suggestion_lines) {
            this.push(line);
        }
    }

    attach_many(suggestions: Suggestion[]): void {
        for (const suggestion of suggestions) {
            let suggestion_line;
            if (this.base.length === 0) {
                suggestion_line = [suggestion];
            } else {
                // When we add a user to a user group, we
                // replace the last pill.
                const last_base_term = this.base.at(-1)!;
                const last_base_string = last_base_term.search_string;
                const new_search_string = suggestion.search_string;
                if (
                    new_search_string.startsWith("dm:") &&
                    new_search_string.includes(last_base_string)
                ) {
                    suggestion_line = [...this.base.slice(0, -1), suggestion];
                } else {
                    suggestion_line = [...this.base, suggestion];
                }
            }
            this.push(suggestion_line);
        }
    }

    get_result(): Suggestion[] {
        return this.result.map((suggestion_line) => {
            const description_htmls = [];
            const search_strings = [];
            for (const suggestion of suggestion_line) {
                if (suggestion.description_html && suggestion.description_html !== "") {
                    description_htmls.push(suggestion.description_html);
                }
                if (suggestion.search_string !== "") {
                    search_strings.push(suggestion.search_string);
                }
            }
            return {
                // We only display description_html for suggestion lines
                // with only one suggestion.
                description_html:
                    description_htmls.length === 1 ? util.the(description_htmls) : undefined,
                search_string: search_strings.join(" "),
            };
        });
    }
}

export function search_term_description_html(item: NarrowTerm): string {
    return `search for ${Handlebars.Utils.escapeExpression(item.operand)}`;
}

export function get_search_result(
    pill_search_terms: NarrowTerm[],
    text_search_terms: NarrowTerm[],
    add_current_filter = false,
): Suggestion[] {
    let suggestion_line: SuggestionLine;
    text_search_terms = text_search_terms.map((term) => Filter.canonicalize_term(term));
    // search_terms correspond to the terms for the query in the input.
    // This includes the entire query entered in the searchbox.
    // terms correspond to the terms for the entire query entered in the searchbox.
    let all_search_terms = [...pill_search_terms, ...text_search_terms];

    // `last` will always be a text term, not a pill term. If there is no
    // text, then `last` is this default empty term.
    let last: NarrowTerm = {operator: "", operand: "", negated: false};
    if (text_search_terms.length > 0) {
        last = text_search_terms.at(-1)!;
    }

    const person_suggestion_ops = ["sender", "dm", "dm-including", "from", "pm-with"];

    // Handle spaces in person name in new suggestions only. Checks if the last operator is 'search'
    // and the second last operator in search_terms is one out of person_suggestion_ops.
    // e.g for `sender:Ted sm`, initially last = {operator: 'search', operand: 'sm'....}
    // and second last is {operator: 'sender', operand: 'sm'....}. If the second last operand
    // is an email of a user, both of these terms remain unchanged. Otherwise search operator
    // will be deleted and new last will become {operator:'sender', operand: 'Ted sm`....}.
    if (
        text_search_terms.length > 1 &&
        last.operator === "search" &&
        person_suggestion_ops.includes(text_search_terms.at(-2)!.operator)
    ) {
        const person_op = text_search_terms.at(-2)!;
        if (!people.reply_to_to_user_ids_string(person_op.operand)) {
            last = {
                operator: person_op.operator,
                operand: person_op.operand + " " + last.operand,
                negated: person_op.negated,
            };
            text_search_terms.splice(-2);
            text_search_terms.push(last);
            all_search_terms = [...pill_search_terms, ...text_search_terms];
        }
    }

    const base_terms = [...pill_search_terms, ...text_search_terms.slice(0, -1)];
    const base = get_default_suggestion_line(base_terms);
    const attacher = new Attacher(base, all_search_terms.length === 0, add_current_filter);

    // Display the default first, unless it has invalid terms.
    if (last.operator === "search") {
        suggestion_line = [
            {
                search_string: last.operand,
                description_html: search_term_description_html(last),
            },
        ];
        attacher.push([...attacher.base, ...suggestion_line]);
    } else if (
        all_search_terms.length > 0 &&
        all_search_terms.every((term) => Filter.is_valid_search_term(term))
    ) {
        suggestion_line = get_default_suggestion_line(all_search_terms);
        attacher.push(suggestion_line);
    }

    // only make one people_getter to avoid duplicate work
    const people_getter = make_people_getter(last);

    function get_people(
        flavor: string,
    ): (last: NarrowTerm, base_terms: NarrowTerm[]) => Suggestion[] {
        return function (last: NarrowTerm, base_terms: NarrowTerm[]): Suggestion[] {
            return get_person_suggestions(people_getter, last, base_terms, flavor);
        };
    }

    // Remember to update the spectator list when changing this.
    let filterers = [
        // This should show before other `get_people` suggestions
        // because both are valid suggestions for typing a user's
        // name, and if there's already has a DM pill then the
        // searching user probably is looking to make a group DM.
        get_group_suggestions,
        get_channels_filter_suggestions,
        get_is_filter_suggestions,
        get_sent_by_me_suggestions,
        get_channel_suggestions,
        get_people("dm"),
        get_people("sender"),
        get_people("dm-including"),
        get_people("from"),
        get_topic_suggestions,
        get_operator_suggestions,
        get_has_filter_suggestions,
    ];

    if (page_params.is_spectator) {
        filterers = [
            get_is_filter_suggestions,
            get_channel_suggestions,
            get_people("sender"),
            get_people("from"),
            get_topic_suggestions,
            get_operator_suggestions,
            get_has_filter_suggestions,
        ];
    }

    const max_items = max_num_of_search_results;

    for (const filterer of filterers) {
        if (attacher.result.length < max_items) {
            const suggestions = filterer(last, base_terms);
            attacher.attach_many(suggestions);
        }
    }

    if (attacher.result.length < max_items) {
        const subset_suggestions = get_term_subset_suggestions(all_search_terms);
        const subset_suggestion_lines = subset_suggestions.map((suggestion) => [suggestion]);
        attacher.push_many(subset_suggestion_lines);
    }
    return attacher.get_result().slice(0, max_items);
}

export let get_suggestions = function (
    pill_search_terms: NarrowTerm[],
    text_search_terms: NarrowTerm[],
    add_current_filter = false,
): {
    strings: string[];
    lookup_table: Map<string, Suggestion>;
} {
    const result = get_search_result(pill_search_terms, text_search_terms, add_current_filter);
    return finalize_search_result(result);
};

export function rewire_get_suggestions(value: typeof get_suggestions): void {
    get_suggestions = value;
}

export function finalize_search_result(result: Suggestion[]): {
    strings: string[];
    lookup_table: Map<string, Suggestion>;
} {
    for (const sug of result) {
        if (sug.description_html) {
            const first = sug.description_html.charAt(0).toUpperCase();
            sug.description_html = first + sug.description_html.slice(1);
        }
    }

    // Typeahead expects us to give it strings, not objects,
    // so we maintain our own hash back to our objects
    const lookup_table = new Map<string, Suggestion>();

    for (const obj of result) {
        lookup_table.set(obj.search_string, obj);
    }

    const strings = result.map((obj: Suggestion) => obj.search_string);
    return {
        strings,
        lookup_table,
    };
}
