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

const channel_incompatible_patterns: TermPattern[] = [
    {operator: "is", operand: "dm"},
    {operator: "channel"},
    {operator: "dm-including"},
    {operator: "dm"},
    {operator: "in"},
    {operator: "channels"},
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

const incompatible_patterns: Partial<Record<NarrowTerm["operator"], TermPattern[]>> &
    Record<
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
        | "has:reaction",
        TermPattern[]
    > = {
    channel: channel_incompatible_patterns,
    stream: channel_incompatible_patterns,
    streams: channel_incompatible_patterns,
    channels: channel_incompatible_patterns,
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
        {operator: "is", operand: "resolved"},
    ],
    "pm-with": [
        {operator: "dm"},
        {operator: "pm-with"},
        {operator: "channel"},
        {operator: "is", operand: "resolved"},
    ],
    "dm-including": [{operator: "channel"}, {operator: "stream"}],
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
    ],
    sender: [{operator: "sender"}, {operator: "from"}],
    from: [{operator: "sender"}, {operator: "from"}],
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
};

// TODO: We have stripped suggestion of all other attributes, we should now
// replace it with simple string in other places.
export type Suggestion = {
    search_string: string;
};

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

function format_as_suggestion(terms: NarrowTerm[]): Suggestion {
    return {
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

function get_channel_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    // For users with "stream" in their muscle memory, still
    // have suggestions with "channel:" operator.
    const valid = ["stream", "channel", "search", ""];
    if (!check_validity(last.operator, terms, valid, incompatible_patterns.channel!)) {
        return [];
    }

    assert(last.operator === "channel" || last.operator === "search" || last.operator === "");

    const query = last.operand;
    let channels = stream_data.subscribed_streams();

    channels = channels.filter((channel_name) => channel_matches_query(channel_name, query));

    channels = typeahead_helper.sorter(query, channels, (x) => x);

    return channels.map((channel_name) => {
        const channel = stream_data.get_sub_by_name(channel_name);
        assert(channel !== undefined);
        const term: NarrowTerm = {
            operator: "channel",
            operand: channel.stream_id.toString(),
            negated: last.negated,
        };
        const search_string = Filter.unparse([term]);
        return {search_string};
    });
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

        return persons.map((person) => {
            const term: NarrowTerm = {
                operator: group_operator,
                operand: all_but_last_part + "," + person.email,
                negated,
            };

            let terms: NarrowTerm[] = [term];
            if (group_operator === "dm" && negated) {
                terms = [{operator: "is", operand: "dm"}, term];
            }

            return {
                search_string: Filter.unparse(terms),
            };
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
    autocomplete_operator: "dm" | "sender" | "dm-including",
): Suggestion[] {
    if (last.operator === "is" && last.operand === "dm") {
        last = {operator: "dm", operand: "", negated: false};
    }

    const valid = ["search", autocomplete_operator];

    if (
        !check_validity(last.operator, terms, valid, incompatible_patterns[autocomplete_operator]!)
    ) {
        return [];
    }

    const persons = people_getter();

    return persons.map((person) => {
        const terms: NarrowTerm[] = [
            {
                operator: autocomplete_operator,
                operand: person.email,
                negated: last.negated,
            },
        ];
        if (last.negated && autocomplete_operator === "dm") {
            // In the special case of "-dm" or "-pm-with", add "is:dm" before
            // it because we assume the user still wants to narrow to direct
            // messages.
            terms.unshift({operator: "is", operand: "dm"});
        }

        return {
            search_string: Filter.unparse(terms),
        };
    });
}

function get_default_suggestion_line(terms: NarrowCanonicalTerm[]): SuggestionLine {
    if (terms.length === 0) {
        return [{search_string: ""}];
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
            incompatible_patterns.topic!,
        )
    ) {
        return [];
    }

    const operand = last.operand;
    const negated = last.operator === "topic" && last.negated;
    let channel_id_str: string | undefined;
    let guess: string | undefined;
    const filter = new Filter(terms);

    // channel:Rome -> show all Rome topics
    // channel:Rome topic: -> show all Rome topics
    // channel:Rome f -> show all Rome topics with a word starting in f
    // channel:Rome topic:f -> show all Rome topics with a word starting in f
    // channel:Rome topic:f -> show all Rome topics with a word starting in f

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
            channel_id_str = operand;
            break;
        case "topic":
        case "search":
            guess = operand;
            if (filter.has_operator("channel")) {
                channel_id_str = filter.terms_with_operator("channel")[0]!.operand;
                // We want to show topics that belong only to the
                // channel mentioned in the `channel` operator, if it exists.
                show_topics_from_other_channels = false;
            } else {
                channel_id_str = narrow_state.stream_id()?.toString();
            }
            break;
    }
    if (!channel_id_str && !show_topics_from_other_channels) {
        return [];
    }

    // We don't want to show topic suggestions from negated channels
    const excluded_channel_ids = new Set(
        terms
            .filter((term) => term.negated && term.operator === "channel")
            .map((term) => term.operand),
    );

    const current_channel_topic_entries: ChannelTopicEntry[] = [];
    if (channel_id_str && !excluded_channel_ids.has(channel_id_str)) {
        // We do this outside the stream_data.subscribed_stream_ids loop,
        // since we could be viewing a channel we can't read.
        const sub = stream_data.get_sub_by_id_string(channel_id_str)!;
        if (sub && stream_data.can_access_topic_history(sub)) {
            const current_channel_id = sub.stream_id;
            stream_topic_history_util.get_server_history(current_channel_id, () => {
                // Fetch topic history from the server, in case we will
                // need it.  Note that we won't actually use the results
                // from the server here for this particular keystroke from
                // the user, because we want to show results immediately.
            });

            for (const topic of stream_topic_history.get_recent_topic_names(current_channel_id)) {
                current_channel_topic_entries.push({channel_id: channel_id_str, topic});
            }
        }
    }

    const other_channel_topic_entries: ChannelTopicEntry[] = [];
    for (const subscribed_channel_id of stream_data.subscribed_stream_ids()) {
        if (
            subscribed_channel_id.toString() === channel_id_str ||
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

type SuggestionAndIncompatiblePatterns = Suggestion & {incompatible_patterns: TermPattern[]};

function get_special_filter_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
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
                    };
                }
                return {
                    ...suggestion,
                    search_string: "-" + suggestion.search_string,
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
            descriptions[s.search_string]?.toLowerCase().startsWith(last_string)
        );
    });
    const filtered_suggestions = suggestions.map(({incompatible_patterns, ...s}) => s);

    return filtered_suggestions;
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
    const suggestions: SuggestionAndIncompatiblePatterns[] = [];

    if (!page_params.is_spectator) {
        suggestions.push({
            search_string: public_channels_search_string,
            incompatible_patterns: incompatible_patterns.channels!,
        });
    }

    if (stream_data.realm_has_web_public_streams()) {
        suggestions.push({
            search_string: web_public_channels_search_string,
            incompatible_patterns: incompatible_patterns.channels!,
        });
    }

    return get_special_filter_suggestions(last, terms, suggestions);
}

function get_is_filter_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    let suggestions: SuggestionAndIncompatiblePatterns[];
    if (page_params.is_spectator) {
        suggestions = [
            {
                search_string: "is:resolved",
                incompatible_patterns: incompatible_patterns["is:resolved"],
            },
            {
                search_string: "-is:resolved",
                incompatible_patterns: incompatible_patterns["-is:resolved"],
            },
        ];
    } else {
        suggestions = [
            {
                search_string: "is:dm",
                incompatible_patterns: incompatible_patterns["is:dm"],
            },
            {
                search_string: "is:starred",
                incompatible_patterns: incompatible_patterns["is:starred"],
            },
            {
                search_string: "is:mentioned",
                incompatible_patterns: incompatible_patterns["is:mentioned"],
            },
            {
                search_string: "is:followed",
                incompatible_patterns: incompatible_patterns["is:followed"],
            },
            {
                search_string: "is:alerted",
                incompatible_patterns: incompatible_patterns["is:alerted"],
            },
            {
                search_string: "is:unread",
                incompatible_patterns: incompatible_patterns["is:unread"],
            },
            {
                search_string: "is:muted",
                incompatible_patterns: incompatible_patterns["is:muted"],
            },
            {
                search_string: "is:resolved",
                incompatible_patterns: incompatible_patterns["is:resolved"],
            },
            {
                search_string: "-is:resolved",
                incompatible_patterns: incompatible_patterns["-is:resolved"],
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

function get_has_filter_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    const suggestions: SuggestionAndIncompatiblePatterns[] = [
        {
            search_string: "has:link",
            incompatible_patterns: incompatible_patterns["has:link"],
        },
        {
            search_string: "has:image",
            incompatible_patterns: incompatible_patterns["has:image"],
        },
        {
            search_string: "has:attachment",
            incompatible_patterns: incompatible_patterns["has:attachment"],
        },
        {
            search_string: "has:reaction",
            incompatible_patterns: incompatible_patterns["has:reaction"],
        },
    ];
    return get_special_filter_suggestions(last, terms, suggestions);
}

function get_sent_by_me_suggestions(
    last: NarrowCanonicalTermSuggestion,
    terms: NarrowCanonicalTerm[],
): Suggestion[] {
    const last_string = Filter.unparse([last]).toLowerCase();
    const negated =
        last.negated === true || (last.operator === "search" && last.operand.startsWith("-"));
    const negated_symbol = negated ? "-" : "";

    const sender_query = negated_symbol + "sender:" + people.my_current_email();
    const sender_me_query = negated_symbol + "sender:me";
    const from_string = negated_symbol + "from";
    const sent_string = negated_symbol + "sent";

    if (match_criteria(terms, incompatible_patterns.sender!)) {
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
            },
        ];
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

    let choices: NarrowTerm["operator"][];

    if (last.operator === "") {
        choices = ["channels", "channel", "streams", "stream"];
    } else {
        choices = [
            "channels",
            "channel",
            "topic",
            "dm",
            "dm-including",
            "sender",
            "near",
            "from",
            "pm-with",
            "streams",
            "stream",
        ];
    }

    // We remove suggestion choice if its incompatible_pattern matches
    // that of current search terms.
    choices = choices.filter(
        (choice) =>
            common.phrase_match(last_operand, choice) &&
            (!incompatible_patterns[choice] ||
                !match_criteria(terms, incompatible_patterns[choice])),
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
        const op = [{operator: choice, operand: "", negated}];
        return format_as_suggestion(op);
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
                    (new_search_string.startsWith("dm:") ||
                        new_search_string.startsWith("dm-including:")) &&
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
            const search_strings = [];
            for (const suggestion of suggestion_line) {
                if (suggestion.search_string !== "") {
                    search_strings.push(suggestion.search_string);
                }
            }
            return {
                search_string: search_strings.join(" "),
            };
        });
    }
}

export function search_term_description_html(operand: string): string {
    return `search for ${Handlebars.Utils.escapeExpression(operand)}`;
}

export function get_search_result(
    pill_search_terms: NarrowCanonicalTerm[],
    text_search_terms_non_canonical: NarrowTermSuggestion[],
    add_current_filter = false,
): Suggestion[] {
    let suggestion_line: SuggestionLine;
    const text_search_terms: NarrowCanonicalTermSuggestion[] = text_search_terms_non_canonical.map(
        (term) =>
            Filter.convert_suggestion_to_term(term) ?? {
                operator: filter_util.canonicalize_operator(term.operator),
                operand: term.operand,
                negated: term.negated,
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

    const person_suggestion_ops = ["sender", "dm", "dm-including"];

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
        suggestion_line = [
            {
                search_string: last.operand,
            },
        ];
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

    // only make one people_getter to avoid duplicate work
    const people_getter = make_people_getter(last);

    function get_people(
        flavor: "dm" | "sender" | "dm-including",
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

    const max_items = max_num_of_search_results;

    for (const filterer of filterers) {
        if (attacher.result.length < max_items) {
            const suggestions = filterer(last, base_terms);
            attacher.attach_many(suggestions);
        }
    }

    return attacher.get_result().slice(0, max_items);
}

export let get_suggestions = function (
    pill_search_terms: NarrowCanonicalTerm[],
    text_search_terms: NarrowTermSuggestion[],
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
