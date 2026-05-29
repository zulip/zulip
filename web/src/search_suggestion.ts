import Handlebars from "handlebars/runtime.js";
import assert from "minimalistic-assert";

import {MAX_ITEMS} from "./bootstrap_typeahead.ts";
import * as common from "./common.ts";
import * as direct_message_group_data from "./direct_message_group_data.ts";
import {Filter} from "./filter.ts";
import * as filter_util from "./filter_util.ts";
import * as narrow_state from "./narrow_state.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import {RESOLVED_TOPIC_PREFIX} from "./resolved_topic.ts";
import type {
    NarrowCanonicalOperator,
    NarrowCanonicalTerm,
    NarrowCanonicalTermSuggestion,
    NarrowTerm,
    NarrowTermSuggestion,
} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import * as util from "./util.ts";

type ChannelTopicEntry = {
    channel_id: string;
    topic: string;
};

type TermPattern = Omit<NarrowTerm, "operand"> & Partial<Pick<NarrowTerm, "operand">>;

const common_incompatible_patterns: TermPattern[] = [
    {operator: "is", operand: "dm"},
    {operator: "channel"},
    {operator: "dm-including"},
    {operator: "dm"},
    {operator: "in"},
];

const channel_incompatible_patterns: TermPattern[] = [
    ...common_incompatible_patterns,
    {operator: "channels"},
];

const channels_public_incompatible_patterns: TermPattern[] = [
    ...common_incompatible_patterns,
    {operator: "channels", operand: "public"},
    {operator: "channels", operand: "web-public"},
];

// TODO: Expand this to support all available filters and its description.
// Also, we generate some descriptions in filter.ts too, we should look to
// refactor them together.
// Note: This list only contains search_strings used in `get_special_filters_suggestion`
// since only their corresponding descriptions are matched with search query.
const descriptions: Record<string, string> = {
    "is:resolved": "resolved topics",
    "-is:resolved": "unresolved topics",
    "is:dm": "direct messages",
    "is:starred": "starred messages",
    "is:mentioned": "messages that mention you",
    "is:followed": "followed topics",
    "is:alerted": "alerted messages",
    "is:unread": "unread messages",
    "is:muted": "muted messages",
    "has:link": "messages with links",
    "has:image": "messages with images",
    "has:attachment": "messages with attachments",
    "has:reaction": "messages with reactions",
};

type SearchFilter =
    | NarrowCanonicalOperator
    | "channels:public"
    | "channels:web-public"
    | "channels:archived"
    | "is:resolved"
    | "-is:resolved"
    | "is:dm"
    | "is:starred"
    | "is:mentioned"
    | "is:followed"
    | "is:alerted"
    | "is:unread"
    | "is:muted"
    | "has:link"
    | "has:image"
    | "has:attachment"
    | "has:reaction";

const incompatible_patterns: Record<SearchFilter, TermPattern[]> = {
    channel: channel_incompatible_patterns,
    channels: channel_incompatible_patterns,
    "channels:public": channels_public_incompatible_patterns,
    "channels:web-public": channels_public_incompatible_patterns,
    "channels:archived": [
        ...common_incompatible_patterns,
        {operator: "channels", operand: "archived"},
    ],
    topic: [
        {operator: "dm"},
        {operator: "is", operand: "dm"},
        {operator: "dm-including"},
        {operator: "topic"},
    ],
    dm: [
        {operator: "dm"},
        {operator: "pm-with"},
        {operator: "channel"},
        {operator: "channels"},
        {operator: "is", operand: "resolved"},
    ],
    "dm-including": [{operator: "channel"}, {operator: "stream"}, {operator: "channels"}],
    "is:resolved": [
        {operator: "is", operand: "resolved"},
        {operator: "is", operand: "dm"},
        {operator: "dm"},
        {operator: "dm-including"},
    ],
    "-is:resolved": [
        {operator: "is", operand: "resolved"},
        {operator: "is", operand: "dm"},
        {operator: "dm"},
        {operator: "dm-including"},
    ],
    "is:dm": [
        {operator: "is", operand: "dm"},
        {operator: "is", operand: "resolved"},
        {operator: "channel"},
        {operator: "dm"},
        {operator: "in"},
        {operator: "topic"},
        {operator: "channels"},
    ],
    mentions: [{operator: "mentions"}],
    sender: [{operator: "sender"}, {operator: "from"}],
    "is:starred": [{operator: "is", operand: "starred"}],
    "is:mentioned": [{operator: "is", operand: "mentioned"}],
    "is:followed": [
        {operator: "is", operand: "followed"},
        {operator: "is", operand: "dm"},
        {operator: "dm"},
        {operator: "dm-including"},
    ],
    "is:alerted": [{operator: "is", operand: "alerted"}],
    "is:unread": [{operator: "is", operand: "unread"}],
    "is:muted": [
        {operator: "is", operand: "muted"},
        {operator: "in", operand: "home"},
    ],
    "has:link": [{operator: "has", operand: "link"}],
    "has:image": [{operator: "has", operand: "image"}],
    "has:attachment": [{operator: "has", operand: "attachment"}],
    "has:reaction": [{operator: "has", operand: "reaction"}],
    near: [],
    // These below are not currently looked up.
    has: [],
    in: [],
    "": [],
    id: [],
    is: [],
    search: [],
    with: [],
};

export type Suggestion = string;

// Operators whose operand identifies a person. When the user types a
// space inside one (e.g. `sender:Ted Smith`), the typeahead merges the
// trailing `search:` token into the preceding operator so the multi-word
// name can be matched.
const PERSON_OPS: ReadonlySet<NarrowCanonicalOperator> = new Set([
    "sender",
    "dm",
    "dm-including",
    "mentions",
]);

// If `text_search_terms` ends in `<operator>:<word1> search:<word2>` where
// `operator` is in `supported_ops`, return the combined `<operator>:<word1>
// <word2>` term. The caller uses this to replace the two trailing terms
// with the merged one, so the multi-word operand can be matched.
function compute_multi_word_merged_term(
    text_search_terms: NarrowCanonicalTermSuggestion[],
    supported_ops: ReadonlySet<NarrowCanonicalOperator>,
): NarrowCanonicalTermSuggestion | undefined {
    if (text_search_terms.length < 2) {
        return undefined;
    }
    const last = text_search_terms.at(-1)!;
    const prev = text_search_terms.at(-2)!;
    if (last.operator !== "search" || !supported_ops.has(prev.operator)) {
        return undefined;
    }
    // For `channel:`, the operand reaching this function may already
    // be a `stream_id` (resolved by an earlier search-bar step). Use
    // the channel's name when building the multi-word query so that
    // typing `channel:core t` (visually) matches the "core team"
    // channel even though `prev.operand` is the resolved stream_id,
    // not the typed name.
    let prev_operand_for_match = prev.operand;
    if (prev.operator === "channel") {
        const sub = stream_data.get_sub_by_id_string(prev.operand);
        if (sub !== undefined) {
            prev_operand_for_match = sub.name;
        }
    }
    return {
        operator: prev.operator,
        operand: prev_operand_for_match + " " + last.operand,
        negated: prev.negated,
    };
}

export let max_num_of_search_results = MAX_ITEMS;
export function rewire_max_num_of_search_results(value: typeof max_num_of_search_results): void {
    max_num_of_search_results = value;
}

function channel_matches_query(channel_name: string, q: string): boolean {
    return common.phrase_match(q, channel_name);
}

function match_criteria(terms: NarrowCanonicalTerm[], criteria: TermPattern[]): boolean {
    const filter = new Filter(terms);
    return criteria.some((cr) => {
        if (cr.operand !== undefined) {
            return filter.has_operand(cr.operator, cr.operand);
        }
        return filter.has_operator(cr.operator);
    });
}

function filter_suggestions_by_criteria(
    terms: NarrowCanonicalTerm[],
    search_filters: SearchFilter[],
): Suggestion[] {
    return search_filters.filter(
        (search_filter) => !match_criteria(terms, incompatible_patterns[search_filter]),
    );
}

function check_validity(
    last_operator: NarrowCanonicalOperator,
    terms: NarrowCanonicalTerm[],
    valid: string[],
    incompatible_patterns: TermPattern[],
): boolean {
    // valid: list of strings valid for the last operator
    // incompatible_patterns: list of terms incompatible for any previous terms except last.
    if (!valid.includes(last_operator)) {
        return false;
    }
    if (match_criteria(terms, incompatible_patterns)) {
        return false;
    }
    return true;
}

function format_as_suggestion(terms: NarrowTerm[], is_operator_suggestion = false): Suggestion {
    return Filter.unparse(terms, is_operator_suggestion);
}

function compare_by_direct_message_group(
    valid_user_ids: number[],
): (person1: User, person2: User) => number {
    assert(people.is_valid_user_ids(valid_user_ids));
    // Construct dict for all direct message groups, so we can
    // look up each's recency
    const direct_message_groups = direct_message_group_data.get_direct_message_groups();
    const direct_message_group_dict = new Map<string, number>();
    for (const [i, direct_message_group] of direct_message_groups.entries()) {
        direct_message_group_dict.set(direct_message_group, i + 1);
    }

    return function (person1: User, person2: User): number {
        const direct_message_group1 = people.concat_direct_message_group(
            valid_user_ids,
            person1.user_id,
        );
        const direct_message_group2 = people.concat_direct_message_group(
            valid_user_ids,
            person2.user_id,
        );
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

function get_channel_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    // For users with "stream" in their muscle memory, still
    // have suggestions with "channel:" operator.
    const valid = ["stream", "channel", "search", ""];
    if (!check_validity(last.operator, terms, valid, incompatible_patterns.channel)) {
        return [];
    }

    assert(last.operator === "channel" || last.operator === "search" || last.operator === "");

    const query = last.operand;
    const channel_names = stream_data.subscribed_stream_names();
    let matching_channel_names = channel_names.filter((channel_name) =>
        channel_matches_query(channel_name, query),
    );
    matching_channel_names = typeahead_helper.sorter(query, matching_channel_names, (x) => x);
    return matching_channel_names.map((channel_name) => {
        const channel = stream_data.get_sub_by_name(channel_name);
        assert(channel !== undefined);
        const term: NarrowTerm = {
            operator: "channel",
            operand: channel.stream_id.toString(),
            negated: last.negated,
        };
        const search_string = Filter.unparse([term]);
        return search_string;
    });
}

// Find subscribed channels whose name matches the multi-word `query`,
// and split them into "strong" (name starts with the full query,
// case-insensitive) and "weak" (matches but is not a prefix).
function get_channel_multi_word_matches(
    query: string,
    negated: boolean,
): {strong: Suggestion[]; weak: Suggestion[]} {
    const unsorted_matching_channel_names = stream_data
        .subscribed_stream_names()
        .filter((channel_name) => channel_matches_query(channel_name, query));
    const channel_names = typeahead_helper.sorter(query, unsorted_matching_channel_names, (x) => x);

    const strong: Suggestion[] = [];
    const weak: Suggestion[] = [];
    const query_lower = query.toLowerCase();
    for (const channel_name of channel_names) {
        const channel = stream_data.get_sub_by_name(channel_name);
        assert(channel !== undefined);
        const suggestion = Filter.unparse([
            {operator: "channel", operand: channel.stream_id.toString(), negated},
        ]);
        if (channel_name.toLowerCase().startsWith(query_lower)) {
            strong.push(suggestion);
        } else {
            weak.push(suggestion);
        }
    }
    return {strong, weak};
}

function get_group_suggestions(
    group_operator: "dm" | "dm-including",
): (last: NarrowCanonicalTermSuggestion, terms: NarrowCanonicalTerm[]) => Suggestion[] {
    return (last: NarrowCanonicalTermSuggestion, terms: NarrowCanonicalTerm[]): Suggestion[] => {
        // We only suggest groups once a term with a valid user already exists
        if (terms.length === 0) {
            return [];
        }
        const last_complete_term = terms.at(-1)!;
        if (
            !check_validity(
                last_complete_term.operator,
                terms.slice(-1),
                [group_operator],
                [{operator: "channel"}],
            )
        ) {
            return [];
        }
        assert(last_complete_term.operator === group_operator);

        let new_query: string;
        let existing_user_ids: number[];

        // If they started typing since a user pill, we'll parse that as "search"
        // but they might actually want to parse that as a user instead to add to
        // the most recent pill. So we shuffle some things around to support that.
        if (last.operator === "search") {
            new_query = last.operand;
            existing_user_ids = last_complete_term.operand;
            terms = terms.slice(-1);
        } else if (last.operator === "") {
            // User hasn't started typing the next term yet; use the
            // last complete term to generate suggestions.
            assert(last.operand === "");
            new_query = "";
            existing_user_ids = last_complete_term.operand;
        } else {
            // If they already started another term with an other operator, we're
            // no longer dealing with a group DM situation.
            return [];
        }

        // Somehow an invalid user id is showing up earlier in the group.
        // This can happen if e.g. the user manually enters multiple user ids.
        // We won't have group suggestions built from an invalid user, so
        // return an empty list.
        if (!people.is_valid_user_ids(existing_user_ids)) {
            return [];
        }

        // We don't suggest a person if their user id is already present in the
        // operand (not including the last part).
        const person_matcher = people.build_person_matcher(new_query);
        let persons = people.filter_all_persons((person) => {
            if (person.user_id === people.my_current_user_id()) {
                return false;
            }

            if (existing_user_ids.includes(person.user_id)) {
                return false;
            }
            return new_query === "" || person_matcher(person);
        });

        persons.sort(compare_by_direct_message_group(existing_user_ids));

        // Take top 15 persons, since they're ordered by pm_recipient_count.
        persons = persons.slice(0, 15);

        return persons.map((person) => {
            const term: NarrowCanonicalTerm = {
                operator: group_operator,
                operand: [...existing_user_ids, person.user_id],
                negated: last_complete_term.negated,
            };

            let terms: NarrowCanonicalTerm[] = [term];
            if (group_operator === "dm" && last_complete_term.negated) {
                terms = [{operator: "is", operand: "dm"}, term];
            }

            return Filter.unparse(terms);
        });
    };
}

function make_people_getter(last: NarrowCanonicalTermSuggestion): () => User[] {
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

function get_person_suggestions(
    people_getter: () => User[],
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
    autocomplete_operator: "dm" | "sender" | "dm-including" | "mentions",
): Suggestion[] {
    if (last.operator === "is" && last.operand === "dm") {
        last = {operator: "dm", operand: "", negated: false};
    }

    const valid = ["search", autocomplete_operator];

    if (
        !check_validity(last.operator, terms, valid, incompatible_patterns[autocomplete_operator])
    ) {
        return [];
    }

    const persons = people_getter();

    return persons.map((person) => {
        const terms: NarrowCanonicalTerm[] = [];
        switch (autocomplete_operator) {
            case "dm":
            case "dm-including":
                terms.push({
                    operator: autocomplete_operator,
                    operand: [person.user_id],
                    negated: last.negated,
                });
                break;
            case "sender":
            case "mentions":
                terms.push({
                    operator: autocomplete_operator,
                    operand: person.user_id,
                    negated: last.negated,
                });
                break;
        }

        if (last.negated && autocomplete_operator === "dm") {
            // In the special case of "-dm" or "-pm-with", add "is:dm" before
            // it because we assume the user still wants to narrow to direct
            // messages.
            terms.unshift({operator: "is", operand: "dm"});
        }

        return Filter.unparse(terms);
    });
}

function get_default_suggestion_line(terms: NarrowCanonicalTerm[]): SuggestionLine {
    if (terms.length === 0) {
        return [""];
    }
    const suggestion_line = [];
    const suggestion_strings = new Set();
    for (const term of terms) {
        const suggestion = format_as_suggestion([term]);
        if (!suggestion_strings.has(suggestion)) {
            suggestion_line.push(suggestion);
            suggestion_strings.add(suggestion);
        }
    }
    return suggestion_line;
}

export function get_topic_suggestions_from_candidates({
    candidate_topic_entries,
    guess,
}: {
    candidate_topic_entries: ChannelTopicEntry[];
    guess: string;
}): ChannelTopicEntry[] {
    // This function is exported for unit testing purposes.
    const max_num_topics = 10;

    if (guess === "") {
        // In the search UI, once you autocomplete the channel,
        // we just show you the most recent topics before you even
        // need to start typing any characters.
        return candidate_topic_entries.slice(0, max_num_topics);
    }

    // Once the user starts typing characters for a topic name,
    // it is pretty likely they want to get suggestions for
    // topics that may be fairly low in our list of candidates,
    // so we do an aggressive search here.
    //
    // The following loop can be expensive if you have lots
    // of topics in a channel, so we try to exit the loop as
    // soon as we find enough matches.
    const topic_entries: ChannelTopicEntry[] = [];
    for (const candidate_topic_entry of candidate_topic_entries) {
        const topic_name = candidate_topic_entry.topic;

        const topic_display_name = util.get_final_topic_display_name(topic_name);
        if (common.phrase_match(guess, topic_display_name)) {
            topic_entries.push({channel_id: candidate_topic_entry.channel_id, topic: topic_name});
            if (topic_entries.length >= max_num_topics) {
                break;
            }
        }
    }

    return topic_entries;
}

function ignore_resolved_topic_prefix(entry: ChannelTopicEntry, case_insensitive = false): string {
    let topic_name = entry.topic;
    if (topic_name.startsWith(RESOLVED_TOPIC_PREFIX)) {
        topic_name = topic_name.slice(2);
    }
    if (case_insensitive) {
        return topic_name.toLowerCase();
    }
    return topic_name;
}

function get_topic_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    if (
        !check_validity(
            last.operator,
            terms,
            ["channel", "topic", "search"],
            incompatible_patterns.topic,
        )
    ) {
        return [];
    }

    const operand = last.operand;
    const negated = last.operator === "topic" && last.negated;
    // For the case where the channel operator is the last
    // term, the operand may just be a string and is not
    // guaranteed to always be a channel id in a string format.
    // We use a name that represents this .
    let channel_id_or_operand_str: string | undefined;
    let guess: string | undefined;
    const filter = new Filter(terms);

    // channel:Rome -> show all Rome topics
    // channel:Rome topic: -> show all Rome topics
    // channel:Rome f -> show all Rome topics with a word starting in f
    // channel:Rome topic:f -> show all Rome topics with a word starting in f
    // channel:Rome topic:f -> show all Rome topics with a word starting in f
    // channel:NonExistentChannel -> no topic suggestions.

    // When narrowed to a channel:
    //   topic: -> show topics from all subscribed channels with the current channel's
    //   matching topics listed first.
    //   foo -> show all topics in current channel with words starting with foo

    // If somebody explicitly types search:, then we might
    // not want to suggest topics, but I feel this is a very
    // minor issue, and Filter.parse() is currently lossy
    // in terms of telling us whether they provided the operator,
    // i.e. "foo" and "search:foo" both become [{operator: 'search', operand: 'foo'}].

    let show_topics_from_other_channels = true;
    switch (last.operator) {
        case "channel":
            guess = "";
            channel_id_or_operand_str = operand;
            break;
        case "topic":
        case "search":
            guess = operand;
            if (filter.has_operator("channel")) {
                channel_id_or_operand_str = filter.terms_with_operator("channel")[0]!.operand;
                // We want to show topics that belong only to the
                // channel mentioned in the `channel` operator, if it exists.
                show_topics_from_other_channels = false;
            } else {
                channel_id_or_operand_str = narrow_state.stream_id()?.toString();
            }
            break;
    }

    if (!channel_id_or_operand_str && !show_topics_from_other_channels) {
        return [];
    }

    // Avoid sending topic suggestions when the user is
    // just trying to search through channels.
    if (channel_id_or_operand_str?.length === 0 && last.operator === "channel") {
        return [];
    }

    // We don't want to show topic suggestions from negated channels
    const excluded_channel_ids = new Set(
        terms
            .filter((term) => term.negated && term.operator === "channel")
            .map((term) => term.operand),
    );

    const current_channel_topic_entries: ChannelTopicEntry[] = [];
    if (channel_id_or_operand_str && !excluded_channel_ids.has(channel_id_or_operand_str)) {
        // We do this outside the stream_data.subscribed_stream_ids loop,
        // since we could be viewing a channel we can't read.
        const sub = stream_data.get_sub_by_id_string(channel_id_or_operand_str);
        if (sub === undefined && last.operator === "channel") {
            // Since the channel_id_or_operand_str is not a
            // valid channel id we avoid sending any topic
            // suggestions for a channel as the last term.
            return [];
        }
        if (sub && stream_data.can_access_topic_history(sub)) {
            const current_channel_id = sub.stream_id;
            stream_topic_history_util.get_server_history(current_channel_id, () => {
                // Fetch topic history from the server, in case we will
                // need it.  Note that we won't actually use the results
                // from the server here for this particular keystroke from
                // the user, because we want to show results immediately.
            });

            for (const topic of stream_topic_history.get_recent_topic_names(current_channel_id)) {
                current_channel_topic_entries.push({channel_id: channel_id_or_operand_str, topic});
            }
        }
    }

    const other_channel_topic_entries: ChannelTopicEntry[] = [];
    for (const subscribed_channel_id of stream_data.subscribed_stream_ids()) {
        if (
            subscribed_channel_id.toString() === channel_id_or_operand_str ||
            excluded_channel_ids.has(subscribed_channel_id.toString())
        ) {
            continue;
        } else if (!show_topics_from_other_channels) {
            continue;
        }

        for (const topic of stream_topic_history.get_recent_topic_names(subscribed_channel_id)) {
            other_channel_topic_entries.push({
                channel_id: subscribed_channel_id.toString(),
                topic,
            });
        }
    }

    assert(guess !== undefined);

    let current_channel_topic_suggestion_entries = get_topic_suggestions_from_candidates({
        candidate_topic_entries: current_channel_topic_entries,
        guess,
    });
    let other_channel_topic_suggestion_entries = get_topic_suggestions_from_candidates({
        candidate_topic_entries: other_channel_topic_entries,
        guess,
    });

    // When the guess is non-empty, we rely on `typeaheader_helper.sorter` to give the same
    // experience as composebox_typeahead.
    // Else we sort in a case-insensitive fashion.
    if (guess.length > 0) {
        current_channel_topic_suggestion_entries = typeahead_helper.sorter(
            guess,
            current_channel_topic_suggestion_entries,
            ignore_resolved_topic_prefix,
        );
        other_channel_topic_suggestion_entries = typeahead_helper.sorter(
            guess,
            other_channel_topic_suggestion_entries,
            ignore_resolved_topic_prefix,
        );
    } else {
        current_channel_topic_suggestion_entries =
            current_channel_topic_suggestion_entries.toSorted((a, b) =>
                ignore_resolved_topic_prefix(a, true).localeCompare(
                    ignore_resolved_topic_prefix(b, true),
                ),
            );
        other_channel_topic_suggestion_entries = other_channel_topic_suggestion_entries.toSorted(
            (a, b) =>
                ignore_resolved_topic_prefix(a, true).localeCompare(
                    ignore_resolved_topic_prefix(b, true),
                ),
        );
    }
    // We want to rank topics from the current channel higher
    const topics = [
        ...current_channel_topic_suggestion_entries,
        ...other_channel_topic_suggestion_entries,
    ];
    return topics.map((topic) => {
        const topic_term: NarrowTerm = {operator: "topic", operand: topic.topic, negated};
        const terms: NarrowTerm[] = [{operator: "channel", operand: topic.channel_id}, topic_term];
        // We don't want to have two channel pills in the search suggestion.
        if (filter.has_operator("channel")) {
            terms.splice(0, 1);
        }

        return format_as_suggestion(terms);
    });
}

function get_special_filter_suggestions(
    last: NarrowCanonicalTermSuggestion,
    suggestions: Suggestion[],
): Suggestion[] {
    const is_search_operand_negated = last.operator === "search" && last.operand.startsWith("-");
    // Negating suggestions on is_search_operand_negated is required for
    // suggesting negated terms.
    if (last.negated === true || is_search_operand_negated) {
        suggestions = suggestions
            .filter((suggestion) => suggestion !== "-is:resolved")
            .map((suggestion) => "-" + suggestion);
    }

    const last_string = Filter.unparse([last]).toLowerCase();
    suggestions = suggestions.filter((s) => {
        if (last_string === "") {
            return true;
        }

        // returns the substring after the ":" symbol.
        const suggestion_operand = s.slice(s.indexOf(":") + 1);
        // e.g for `att` search query, `has:attachment` should be suggested.
        const show_operator_suggestions =
            last.operator === "search" && suggestion_operand.toLowerCase().startsWith(last_string);
        return (
            s.toLowerCase().startsWith(last_string) ||
            show_operator_suggestions ||
            descriptions[s]?.toLowerCase().startsWith(last_string)
        );
    });

    return suggestions;
}

function get_channels_filter_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    if (last.operator !== "channels") {
        return [];
    }
    const public_channels_search_string = "channels:public";
    const web_public_channels_search_string = "channels:web-public";
    const archived_channels_search_string = "channels:archived";
    const suggestions: Suggestion[] = [];

    if (!page_params.is_spectator) {
        suggestions.push(...filter_suggestions_by_criteria(terms, [public_channels_search_string]));
    }

    if (stream_data.realm_has_web_public_streams()) {
        suggestions.push(
            ...filter_suggestions_by_criteria(terms, [web_public_channels_search_string]),
        );
    }

    suggestions.push(...filter_suggestions_by_criteria(terms, [archived_channels_search_string]));
    return get_special_filter_suggestions(last, suggestions);
}

function get_is_filter_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    let suggestions: Suggestion[];
    if (page_params.is_spectator) {
        suggestions = filter_suggestions_by_criteria(terms, ["is:resolved", "-is:resolved"]);
    } else {
        suggestions = filter_suggestions_by_criteria(terms, [
            "is:dm",
            "is:starred",
            "is:mentioned",
            "is:followed",
            "is:alerted",
            "is:unread",
            "is:muted",
            "is:resolved",
            "-is:resolved",
        ]);
    }
    const special_filtered_suggestions = get_special_filter_suggestions(last, suggestions);
    // Suggest "is:dm" to anyone with "is:private" in their muscle memory
    // if it is compatible with the other terms.
    const other_suggestions = [];
    if (
        suggestions.includes("is:dm") &&
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

function get_has_filter_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    const suggestions: Suggestion[] = filter_suggestions_by_criteria(terms, [
        "has:link",
        "has:image",
        "has:attachment",
        "has:reaction",
    ]);
    return get_special_filter_suggestions(last, suggestions);
}

function get_sent_by_me_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    const last_string = Filter.unparse([last]).toLowerCase();
    const negated =
        last.negated === true || (last.operator === "search" && last.operand.startsWith("-"));
    const negated_symbol = negated ? "-" : "";

    const sender_query = negated_symbol + "sender:" + people.my_current_user_id();
    const sender_email_string = negated_symbol + "sender:" + people.my_current_email();
    const sender_me_query = negated_symbol + "sender:me";
    const from_string = negated_symbol + "from";
    const sent_string = negated_symbol + "sent";

    if (match_criteria(terms, incompatible_patterns.sender)) {
        return [];
    }

    if (
        last.operator === "" ||
        sender_query.startsWith(last_string) ||
        sender_me_query.startsWith(last_string) ||
        from_string.startsWith(last_string) ||
        sender_email_string.startsWith(last_string) ||
        last_string === sent_string
    ) {
        return [sender_query];
    }
    return [];
}

function get_operator_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    if (!(last.operator === "search" || last.operator === "")) {
        return [];
    }
    let last_operand = last.operand;

    let negated = false;
    if (last_operand.startsWith("-")) {
        negated = true;
        last_operand = last_operand.slice(1);
    }

    let canonicalized_operator_choices: NarrowCanonicalOperator[];
    let legacy_operator_choices: NarrowTerm["operator"][];

    const incompatible_operators = new Set<NarrowCanonicalOperator>();

    if (last.operator === "") {
        canonicalized_operator_choices = ["channels", "channel"];
        legacy_operator_choices = ["streams", "stream"];
    } else {
        canonicalized_operator_choices = [
            "channels",
            "channel",
            "topic",
            "dm",
            "dm-including",
            "sender",
            "near",
            "mentions",
        ];
        legacy_operator_choices = ["from", "pm-with", "streams", "stream"];
    }

    // We remove suggestion choice if its incompatible_pattern matches
    // that of current search terms.
    canonicalized_operator_choices = canonicalized_operator_choices.filter((choice) => {
        if (match_criteria(terms, incompatible_patterns[choice])) {
            incompatible_operators.add(choice);
            return false;
        }
        return true;
    });

    // Add equivalent legacy operators for canonicalized operators
    legacy_operator_choices = legacy_operator_choices.filter((choice) => {
        const canonical = filter_util.canonicalize_operator(choice);
        return !incompatible_operators.has(canonical);
    });

    const choices = [...canonicalized_operator_choices, ...legacy_operator_choices].filter(
        (choice) => common.phrase_match(last_operand, choice),
    );

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
        // Map results for "channels:" operator for users
        // who have "streams" in their muscle memory.
        if (choice === "streams") {
            choice = "channels";
        }

        // Set is_operator_suggestion to true, since we're only suggesting
        // the operator and don't want any operand, but we can't put empty
        // strings here for typescript reasons..
        switch (choice) {
            case "dm":
            case "dm-including":
                return format_as_suggestion(
                    [
                        {
                            operator: choice,
                            operand: [],
                            negated,
                        },
                    ],
                    true,
                );
            case "sender":
            case "mentions":
                return format_as_suggestion(
                    [
                        {
                            operator: choice,
                            operand: -1,
                            negated,
                        },
                    ],
                    true,
                );
            default:
                return format_as_suggestion([{operator: choice, operand: "", negated}], true);
        }
    });
}

// One full search suggestion can include multiple search terms, based on what's
// in the search bar.
type SuggestionLine = Suggestion[];
function suggestion_search_string(suggestion_line: SuggestionLine): string {
    const search_strings = [];
    for (let suggestion of suggestion_line) {
        if (suggestion !== "") {
            // This is rendered as "Direct messages" and we want to make sure
            // that we don't add another suggestion for "is:dm" in parallel.
            if (suggestion === "is:private") {
                suggestion = "is:dm";
            }
            search_strings.push(suggestion);
        }
    }
    return search_strings.join(" ");
}

function suggestions_for_empty_search_query(): SuggestionLine[] {
    // Since the context here is an **empty** search query, we assume
    // that there is no `near:` operator. So it's safe to use
    // functions like narrowed_by_topic_reply that return false on
    // conversation views with `near` or `with` operators.
    if (narrow_state.narrowed_by_topic_reply()) {
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
    if (narrow_state.narrowed_by_pm_reply()) {
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
            for (const suggestion of suggestions_for_empty_search_query()) {
                this.push(suggestion);
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

    attach_many(suggestions: Suggestion[], base_override?: SuggestionLine): void {
        const base = base_override ?? this.base;
        for (const suggestion of suggestions) {
            let suggestion_line;
            if (base.length === 0) {
                suggestion_line = [suggestion];
            } else {
                // When we add a user to a user group, we
                // replace the last pill.
                const last_base_term = base.at(-1)!;
                const last_base_string = last_base_term;
                const new_search_string = suggestion;
                if (
                    (new_search_string.startsWith("dm:") ||
                        new_search_string.startsWith("dm-including:")) &&
                    new_search_string.includes(last_base_string)
                ) {
                    suggestion_line = [...base.slice(0, -1), suggestion];
                } else {
                    suggestion_line = [...base, suggestion];
                }
            }
            this.push(suggestion_line);
        }
    }

    get_result(): Suggestion[] {
        return this.result.map((suggestion_line) => {
            const search_strings = [];
            for (const suggestion of suggestion_line) {
                if (suggestion !== "") {
                    search_strings.push(suggestion);
                }
            }
            return search_strings.join(" ");
        });
    }
}

export function search_term_description_html(operand: string): string {
    return `search for ${Handlebars.Utils.escapeExpression(operand)}`;
}

// The canonical list of filterers that the search typeahead runs. The
// list is factored into its own function so that a follow-up commit
// can reuse it from a second code path (the channel multi-word
// suggestion handler) without duplicating the list.
function build_filterer_list(
    last: NarrowCanonicalTermSuggestion,
): ((last: NarrowCanonicalTermSuggestion, terms: NarrowCanonicalTerm[]) => Suggestion[])[] {
    // only make one people_getter to avoid duplicate work
    const people_getter = make_people_getter(last);

    function get_people(
        flavor: "dm" | "sender" | "dm-including" | "mentions",
    ): (last: NarrowCanonicalTermSuggestion, base_terms: NarrowCanonicalTerm[]) => Suggestion[] {
        return function (
            last: NarrowCanonicalTermSuggestion,
            base_terms: NarrowCanonicalTerm[],
        ): Suggestion[] {
            return get_person_suggestions(people_getter, last, base_terms, flavor);
        };
    }

    // Remember to update the spectator list when changing this.
    let filterers = [
        // This should show before other `get_people` suggestions
        // because both are valid suggestions for typing a user's
        // name, and if there's already has a DM pill then the
        // searching user probably is looking to make a group DM.
        get_group_suggestions("dm"),
        get_group_suggestions("dm-including"),
        get_channels_filter_suggestions,
        get_operator_suggestions,
        get_is_filter_suggestions,
        get_sent_by_me_suggestions,
        get_channel_suggestions,
        get_people("dm"),
        get_people("sender"),
        get_people("dm-including"),
        get_people("mentions"),
        get_topic_suggestions,
        get_has_filter_suggestions,
    ];

    if (page_params.is_spectator) {
        filterers = [
            get_channels_filter_suggestions,
            get_operator_suggestions,
            get_is_filter_suggestions,
            get_channel_suggestions,
            get_people("sender"),
            get_topic_suggestions,
            get_has_filter_suggestions,
        ];
    }

    return filterers;
}

// Resolve a `channel:<X>` term to canonical form. The operand can
// arrive in two shapes:
//   - Already canonical (a `stream_id` string, e.g. when the search
//     bar auto-resolved a typed name in an earlier keystroke).
//   - A typed channel name not yet resolved.
// Returns undefined when neither form matches a real channel.
function resolve_channel_term(
    channel_term: NarrowCanonicalTermSuggestion,
): NarrowCanonicalTerm | undefined {
    assert(channel_term.operator === "channel");
    if (stream_data.get_sub_by_id_string(channel_term.operand) !== undefined) {
        return Filter.convert_suggestion_to_term(channel_term);
    }
    // Use the same name lookup as `Filter.parse` so this layer and the
    // parse layer agree on which channel a typed name means.
    const sub = stream_data.get_sub(channel_term.operand);
    if (sub === undefined) {
        return undefined;
    }
    return {
        operator: "channel",
        operand: sub.stream_id.toString(),
        negated: channel_term.negated,
    };
}

// Build a tiered suggestion list when the user types a space inside a
// `channel:` operand (e.g. `channel:automated testing`). The 5-tier
// ranking is:
// 1. The first N "strong" multi-word channel matches (channels whose
//    name starts with the full multi-word query). We only show max N
//    of these in tier 1 so that tiers 2 and 3 stay near the top of
//    the list.
// 2. Completions that interpret the text after the space as the start
//    of a new operator. Only shown when the channel before the space
//    resolves to a real channel.
//    (e.g. `channel:automated h` → `channel:automated has:link`).
// 3. The user's input read as the channel before the space plus the
//    text after as a free-text search (e.g. `channel:automated testing`
//    becomes channel `automated` + text search for `testing`).
// 4. Remaining strong multi-word channel matches.
// 5. "Weak" multi-word matches (phrase-match the full query but
//    don't start with it).

// MAX_STRONG_MULTI_WORD_MATCHES_ABOVE_FREE_TEXT is the N in step 1.
const MAX_STRONG_MULTI_WORD_MATCHES_ABOVE_FREE_TEXT = 2;

function get_suggestions_for_multi_word_channel(
    pill_search_terms: NarrowCanonicalTerm[],
    text_search_terms: NarrowCanonicalTermSuggestion[],
    merged_term: NarrowCanonicalTermSuggestion,
    add_current_filter: boolean,
): Suggestion[] {
    const last = text_search_terms.at(-1)!;
    const prev = text_search_terms.at(-2)!;
    const all_search_terms = [...pill_search_terms, ...text_search_terms];
    const max_items = max_num_of_search_results;

    // Base terms that precede the prev channel term. These are common
    // to both interpretations (merged and un-merged).
    const valid_text_terms_before_prev = text_search_terms
        .slice(0, -2)
        .map((term) => Filter.convert_suggestion_to_term(term))
        .filter((term) => term !== undefined);
    const base_terms_before_prev = [...pill_search_terms, ...valid_text_terms_before_prev];
    const base_line_before_prev = get_default_suggestion_line(base_terms_before_prev);

    // Does the prev term resolve to a real channel? This gates tier 2
    // (suggesting a new operator after the channel only makes sense if
    // the channel itself is real) and tier 3 display (un-resolvable
    // channels are dropped from the suggestion).
    const prev_canonical = resolve_channel_term(prev);

    const attacher = new Attacher(
        base_line_before_prev,
        all_search_terms.length === 0,
        add_current_filter,
    );

    // Base terms/line including the resolved prev term, shared by
    // tiers 2 and 3 and the post-tier filterer loop. When prev
    // doesn't resolve, fall back to the before-prev base.
    const base_terms_with_prev =
        prev_canonical !== undefined
            ? [...base_terms_before_prev, prev_canonical]
            : base_terms_before_prev;
    const base_line_with_prev =
        prev_canonical !== undefined
            ? get_default_suggestion_line(base_terms_with_prev)
            : base_line_before_prev;

    // Tiers 1 / 4 / 5: multi-word channel matches.
    let strong: Suggestion[] = [];
    let weak: Suggestion[] = [];
    if (!match_criteria(base_terms_before_prev, incompatible_patterns.channel)) {
        ({strong, weak} = get_channel_multi_word_matches(
            merged_term.operand,
            merged_term.negated ?? false,
        ));
    }

    // Tier 1: the first N strong multi-word matches. We only show max N
    // here so that tier 3 stays near the top of the list.
    const tier_1 = strong.slice(0, MAX_STRONG_MULTI_WORD_MATCHES_ABOVE_FREE_TEXT);
    const tier_4 = strong.slice(MAX_STRONG_MULTI_WORD_MATCHES_ABOVE_FREE_TEXT);
    for (const suggestion of tier_1) {
        attacher.push([...base_line_before_prev, suggestion]);
    }

    // Tier 2: treat the text after the space as the start of a new
    // operator (e.g. `h` → `has:link`). This is the curated subset of
    // `build_filterer_list` that produces operator-prefix completions.
    // Note: If you're adding a new filterer that produces operator-prefix
    // completions, add it here too for top-of-list visibility — but if you
    // don't, it will still appear via the post-tier-5 loop below.
    if (prev_canonical !== undefined) {
        const tier_2_filterers = [
            get_operator_suggestions,
            get_is_filter_suggestions,
            ...(page_params.is_spectator ? [] : [get_sent_by_me_suggestions]),
            get_has_filter_suggestions,
        ];
        for (const filterer of tier_2_filterers) {
            for (const suggestion of filterer(last, base_terms_with_prev)) {
                attacher.push([...base_line_with_prev, suggestion]);
            }
        }
    }

    // Tier 3: the un-merged reading — `prev` kept as its own channel
    // term plus the trailing fragment as a free-text search (e.g.
    // `channel:automated testing`). When `prev` didn't resolve to a
    // real channel, `base_line_with_prev` already omits it, so the row
    // is just the free-text fragment (e.g. `testing`), matching the
    // default-row behavior for a not-yet-real channel.
    attacher.push([...base_line_with_prev, last.operand]);

    // Tier 4: remaining strong multi-word matches.
    for (const suggestion of tier_4) {
        attacher.push([...base_line_before_prev, suggestion]);
    }

    // Tier 5: weak multi-word matches.
    for (const suggestion of weak) {
        attacher.push([...base_line_before_prev, suggestion]);
    }

    // After the explicit tiers, run the full filterer list with the
    // un-merged interpretation — e.g. topic suggestions within the
    // resolved channel. This re-runs tier 2's operator-prefix
    // filterers, but the Attacher dedupes them.
    for (const filterer of build_filterer_list(last)) {
        if (attacher.result.length < max_items) {
            attacher.attach_many(filterer(last, base_terms_with_prev), base_line_with_prev);
        }
    }

    return attacher.get_result().slice(0, max_items);
}

export let get_suggestions = function (
    pill_search_terms: NarrowCanonicalTerm[],
    text_search_terms_non_canonical: NarrowTermSuggestion[],
    add_current_filter = false,
): Suggestion[] {
    let suggestion_line: SuggestionLine;
    const text_search_terms: NarrowCanonicalTermSuggestion[] = text_search_terms_non_canonical.map(
        (term) => {
            // Try to parse term into canonical form first to
            // perform any necessary conversions.
            const canonical_term = Filter.convert_suggestion_to_term(term);
            if (canonical_term) {
                return {
                    operator: canonical_term.operator,
                    operand: String(canonical_term.operand),
                    negated: canonical_term.negated,
                };
            }
            return {
                operator: filter_util.canonicalize_operator(term.operator),
                operand: term.operand,
                negated: term.negated,
            };
        },
    );
    // search_terms correspond to the terms for the query in the input.
    // This includes the entire query entered in the searchbox.
    // terms correspond to the terms for the entire query entered in the searchbox.
    let all_search_terms = [...pill_search_terms, ...text_search_terms];

    // `last` will always be a text term, not a pill term. If there is no
    // text, then `last` is this default empty term.
    let last: NarrowCanonicalTermSuggestion = {operator: "", operand: "", negated: false};
    if (text_search_terms.length > 0) {
        last = text_search_terms.at(-1)!;
    }

    // Handle spaces inside a `channel:` operand by offering both the
    // multi-word interpretation and the single-word + free-text
    // interpretation, per the 5-tier ranking in
    // `get_suggestions_for_multi_word_channel`. A follow-up commit
    // will apply the same treatment to `topic:`.
    const merged_channel_term = compute_multi_word_merged_term(
        text_search_terms,
        new Set(["channel"]),
    );
    if (merged_channel_term !== undefined) {
        return get_suggestions_for_multi_word_channel(
            pill_search_terms,
            text_search_terms,
            merged_channel_term,
            add_current_filter,
        );
    }

    // Handle spaces inside the operand of a person operator. For e.g.
    // `sender:Ted sm` (parsed as `sender:Ted` + `search:sm`), we merge
    // the two trailing terms into a single `sender:"Ted sm"` term so
    // the multi-word name can match users like "Ted Smith".
    const merged_person_term = compute_multi_word_merged_term(text_search_terms, PERSON_OPS);
    if (merged_person_term !== undefined) {
        last = merged_person_term;
        text_search_terms.splice(-2);
        text_search_terms.push(last);
        all_search_terms = [...pill_search_terms, ...text_search_terms];
    }
    const valid_base_text_search_terms = text_search_terms
        .slice(0, -1)
        .map((term) => Filter.convert_suggestion_to_term(term))
        .filter((term) => term !== undefined);
    const base_terms = [...pill_search_terms, ...valid_base_text_search_terms];
    const base = get_default_suggestion_line(base_terms);
    const attacher = new Attacher(base, all_search_terms.length === 0, add_current_filter);
    const last_term = Filter.convert_suggestion_to_term(last);

    // Display the default first, unless it has invalid terms.
    if (last.operator === "search") {
        suggestion_line = [last.operand];
        attacher.push([...attacher.base, ...suggestion_line]);
    } else if (
        // Check all provided terms are valid.
        all_search_terms.length > 0 &&
        last_term !== undefined &&
        base_terms.length + 1 === all_search_terms.length
    ) {
        suggestion_line = get_default_suggestion_line([...base_terms, last_term]);
        attacher.push(suggestion_line);
    }

    const filterers = build_filterer_list(last);

    const max_items = max_num_of_search_results;

    for (const filterer of filterers) {
        if (attacher.result.length < max_items) {
            const suggestions = filterer(last, base_terms);
            attacher.attach_many(suggestions);
        }
    }

    return attacher.get_result().slice(0, max_items);
};

export function rewire_get_suggestions(value: typeof get_suggestions): void {
    get_suggestions = value;
}
