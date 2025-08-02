import _ from "lodash";
import assert from "minimalistic-assert";

import * as resolved_topic from "../shared/src/resolved_topic.ts";
import render_search_description from "../templates/search_description.hbs";

import * as blueslip from "./blueslip.ts";
import * as hash_parser from "./hash_parser.ts";
import {$t} from "./i18n.ts";
import * as message_parser from "./message_parser.ts";
import * as message_store from "./message_store.ts";
import type {Message} from "./message_store.ts";
import * as muted_users from "./muted_users.ts";
import {page_params} from "./page_params.ts";
import type {User} from "./people.ts";
import * as people from "./people.ts";
import type {UserPillItem} from "./search_suggestion.ts";
import {current_user, realm} from "./state_data.ts";
import type {NarrowTerm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";

type IconData = {
    title?: string | undefined;
    html_title?: string | undefined;
    is_spectator: boolean;
} & (
    | {
          zulip_icon: string;
      }
    | {
          icon: string | undefined;
      }
);

type Part =
    | {
          type: "plain_text";
          content: string;
      }
    | {
          type: "channel_topic";
          channel: string;
          topic_display_name: string;
          is_empty_string_topic: boolean;
      }
    | {
          type: "channel";
          prefix_for_operator: string;
          operand: string;
      }
    | {
          type: "is_operator";
          verb: string;
          operand: string;
      }
    | {
          type: "invalid_has";
          operand: string;
      }
    | {
          type: "prefix_for_operator";
          prefix_for_operator: string;
          operand: string;
          is_empty_string_topic?: boolean;
      }
    | {
          type: "user_pill";
          operator: string;
          users: ValidOrInvalidUser[];
      };

type ValidOrInvalidUser =
    | {valid_user: true; user_pill_context: UserPillItem}
    | {valid_user: false; operand: string};

function zephyr_stream_name_match(
    message: Message & {type: "stream"},
    stream_name: string,
): boolean {
    // Zephyr users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
    // (unsocial, ununsocial, social.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(?:un)*(.+?)(?:\.d)*$/i.exec(stream_name);
    let base_stream_name = stream_name;
    if (m?.[1] !== undefined) {
        base_stream_name = m[1];
    }
    const related_regexp = new RegExp(
        /^(un)*/.source + _.escapeRegExp(base_stream_name) + /(\.d)*$/.source,
        "i",
    );
    const message_stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    return related_regexp.test(message_stream_name);
}

function zephyr_topic_name_match(message: Message & {type: "stream"}, operand: string): boolean {
    // Zephyr users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
    // (foo, foo.d, foo.d.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(.*?)(?:\.d)*$/i.exec(operand);
    // m should never be null because any string matches that regex.
    assert(m !== null);
    const base_topic = m[1]!;
    let related_regexp;

    // Additionally, Zephyr users expect the empty instance and
    // instance "personal" to be the same.
    if (
        base_topic === "" ||
        base_topic.toLowerCase() === "personal" ||
        base_topic.toLowerCase() === '(instance "")'
    ) {
        related_regexp = /^(|personal|\(instance ""\))(\.d)*$/i;
    } else {
        related_regexp = new RegExp(
            /^/.source + _.escapeRegExp(base_topic) + /(\.d)*$/.source,
            "i",
        );
    }

    return related_regexp.test(message.topic);
}

function message_in_home(message: Message): boolean {
    // The home view contains messages not sent to muted channels,
    // with additional logic for unmuted topics and
    // single-channel windows.
    if (message.type === "private") {
        return true;
    }
    const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    if (
        page_params.narrow_stream !== undefined &&
        stream_name.toLowerCase() === page_params.narrow_stream.toLowerCase()
    ) {
        return true;
    }

    return user_topics.is_topic_visible_in_home(message.stream_id, message.topic);
}

function message_matches_search_term(message: Message, operator: string, operand: string): boolean {
    switch (operator) {
        case "has":
            switch (operand) {
                case "image":
                    return message_parser.message_has_image(message.content);
                case "link":
                    return message_parser.message_has_link(message.content);
                case "attachment":
                    return message_parser.message_has_attachment(message.content);
                case "reaction":
                    return message_parser.message_has_reaction(message);
                default:
                    return false; // has:something_else returns false
            }

        case "is":
            switch (operand) {
                case "dm":
                    return message.type === "private";
                case "starred":
                    return message.starred;
                case "mentioned":
                    return message.mentioned;
                case "alerted":
                    return message.alerted;
                case "unread":
                    return message.unread;
                case "resolved":
                    return message.type === "stream" && resolved_topic.is_resolved(message.topic);
                case "followed":
                    return (
                        message.type === "stream" &&
                        user_topics.is_topic_followed(message.stream_id, message.topic)
                    );
                case "muted":
                    return !message_in_home(message);
                default:
                    return false; // is:whatever returns false
            }

        case "in":
            switch (operand) {
                case "home":
                    return message_in_home(message);
                case "all":
                    return true;
                default:
                    return false; // in:whatever returns false
            }

        case "near":
            // this is all handled server side
            return true;

        case "id":
            return message.id.toString() === operand;

        case "channel": {
            if (message.type !== "stream") {
                return false;
            }

            if (realm.realm_is_zephyr_mirror_realm) {
                const stream = stream_data.get_sub_by_id_string(operand);
                return zephyr_stream_name_match(message, stream?.name ?? "");
            }

            return message.stream_id.toString() === operand;
        }

        case "topic":
            if (message.type !== "stream") {
                return false;
            }

            operand = operand.toLowerCase();
            if (realm.realm_is_zephyr_mirror_realm) {
                return zephyr_topic_name_match(message, operand);
            }
            return message.topic.toLowerCase() === operand;

        case "sender":
            return people.id_matches_email_operand(message.sender_id, operand);

        case "dm": {
            // TODO: use user_ids, not emails here
            if (message.type !== "private") {
                return false;
            }
            const operand_ids = people.pm_with_operand_ids(operand);
            if (!operand_ids) {
                return false;
            }
            const user_ids = people.pm_with_user_ids(message);
            if (!user_ids) {
                return false;
            }

            return _.isEqual(operand_ids, user_ids);
        }

        case "dm-including": {
            const operand_user = people.get_by_email(operand);
            if (operand_user === undefined) {
                return false;
            }
            const user_ids = people.all_user_ids_in_pm(message);
            if (!user_ids) {
                return false;
            }
            return user_ids.includes(operand_user.user_id);
        }
    }

    return true; // unknown operators return true (effectively ignored)
}

// For when we don't need to do highlighting
export function create_user_pill_context(user: User): UserPillItem {
    const avatar_url = people.small_avatar_url_for_person(user);

    return {
        id: user.user_id,
        display_value: user.full_name,
        has_image: true,
        img_src: avatar_url,
        should_add_guest_user_indicator: people.should_add_guest_user_indicator(user.user_id),
    };
}

const USER_OPERATORS = new Set([
    "dm-including",
    "dm",
    "sender",
    "from",
    "pm-with",
    "group-pm-with",
]);

export class Filter {
    _terms: NarrowTerm[];
    _sorted_term_types?: string[] = undefined;
    _predicate?: (message: Message) => boolean;
    _can_mark_messages_read?: boolean;
    requires_adjustment_for_moved_with_target?: boolean;
    narrow_requires_hash_change: boolean;
    cached_sorted_terms_for_comparison?: string[] | undefined = undefined;

    constructor(terms: NarrowTerm[]) {
        this._terms = terms;
        this.setup_filter(terms);
        this.requires_adjustment_for_moved_with_target = this.has_operator("with");
        this.narrow_requires_hash_change = false;
    }

    static canonicalize_operator(operator: string): string {
        operator = operator.toLowerCase();

        if (operator === "pm-with") {
            // "pm-with:" was renamed to "dm:"
            return "dm";
        }

        if (operator === "group-pm-with") {
            // "group-pm-with:" was replaced with "dm-including:"
            return "dm-including";
        }

        if (operator === "from") {
            return "sender";
        }

        if (util.is_topic_synonym(operator)) {
            return "topic";
        }

        if (util.is_channel_synonym(operator)) {
            return "channel";
        }

        if (util.is_channels_synonym(operator)) {
            return "channels";
        }
        return operator;
    }

    static canonicalize_term({negated = false, operator, operand}: NarrowTerm): NarrowTerm {
        // Make negated explicitly default to false for both clarity and
        // simplifying deepEqual checks in the tests.
        operator = Filter.canonicalize_operator(operator);

        switch (operator) {
            case "is":
                // "is:private" was renamed to "is:dm"
                if (operand === "private") {
                    operand = "dm";
                }
                break;
            case "has":
                // images -> image, etc.
                operand = operand.replace(/s$/, "");
                break;

            case "channel":
                break;
            case "topic":
                break;
            case "sender":
            case "dm":
                operand = operand.toString().toLowerCase();
                if (operand === "me") {
                    operand = people.my_current_email();
                }
                break;
            case "dm-including":
                operand = operand.toString().toLowerCase();
                break;
            case "search":
                // The mac app automatically substitutes regular quotes with curly
                // quotes when typing in the search bar.  Curly quotes don't trigger our
                // phrase search behavior, however.  So, we replace all instances of
                // curly quotes with regular quotes when doing a search.  This is
                // unlikely to cause any problems and is probably what the user wants.
                operand = operand.toString().replaceAll(/[\u201C\u201D]/g, '"');
                break;
            default:
                operand = operand.toString().toLowerCase();
        }

        // We may want to consider allowing mixed-case operators at some point
        return {
            negated,
            operator,
            operand,
        };
    }

    static ensure_channel_topic_terms(
        orig_terms: NarrowTerm[],
        message: Message,
    ): NarrowTerm[] | undefined {
        // In presence of `with` term without channel or topic terms in the narrow, the
        // narrow is populated with the channel and toipic terms through this operation,
        // so that `with` can be used as a standalone operator to target conversation.
        const contains_with_operator = orig_terms.some((term) => term.operator === "with");

        if (!contains_with_operator) {
            return undefined;
        }

        let contains_channel_term = false;
        let contains_topic_term = false;
        let contains_dm_term = false;

        for (const term of orig_terms) {
            switch (Filter.canonicalize_operator(term.operator)) {
                case "channel":
                    contains_channel_term = true;
                    break;
                case "topic":
                    contains_topic_term = true;
                    break;
                case "dm":
                    contains_dm_term = true;
            }
        }

        // If the narrow is already a channel-topic narrow containing
        // channel and topic terms, we will return undefined now so that
        // it can be adjusted further if needed later.
        if (!contains_dm_term && contains_channel_term && contains_topic_term) {
            return undefined;
        }

        const conversation_terms = new Set(["channel", "topic", "dm"]);

        const non_conversation_terms = orig_terms.filter((term) => {
            const operator = Filter.canonicalize_operator(term.operator);
            return !conversation_terms.has(operator);
        });

        assert(message.type === "stream");

        const channel_term = {operator: "channel", operand: message.stream_id.toString()};
        const topic_term = {operator: "topic", operand: message.topic};

        const updated_terms = [channel_term, topic_term, ...non_conversation_terms];
        return updated_terms;
    }

    /* We use a variant of URI encoding which looks reasonably
       nice and still handles unambiguously cases such as
       spaces in operands.

       This is just for the search bar, not for saving the
       narrow in the URL fragment.  There we do use full
       URI encoding to avoid problematic characters. */
    static encodeOperand(operand: string, operator: string): string {
        if (USER_OPERATORS.has(operator)) {
            return operand.replaceAll(/[\s"%]/g, (c) => encodeURIComponent(c));
        }
        return operand.replaceAll(/[\s"%+]/g, (c) => (c === " " ? "+" : encodeURIComponent(c)));
    }

    static decodeOperand(encoded: string, operator: string): string {
        encoded = encoded.trim().replaceAll('"', "");
        if (!USER_OPERATORS.has(operator)) {
            encoded = encoded.replaceAll("+", " ");
        }
        return util.robust_url_decode(encoded);
    }

    // Parse a string into a list of terms (see below).
    static parse(str: string, for_pills = false): NarrowTerm[] {
        const terms: NarrowTerm[] = [];
        let search_term: string[] = [];
        let negated;
        let operator;
        let operand;
        let term;

        function maybe_add_search_terms(): void {
            if (search_term.length > 0) {
                operator = "search";
                const _operand = search_term.join(" ");
                term = {operator, operand: _operand, negated: false};
                terms.push(term);
                search_term = [];
            }
        }

        // Match all operands that either have no spaces, or are surrounded by
        // quotes, preceded by an optional operator.
        // TODO: rewrite this using `str.matchAll` to get out the match objects
        // with individual capture groups, so we don’t need to write a separate
        // parser with `.split`.
        const matches = str.match(/([^\s:]+:)?("[^"]+"?|\S+)/g);
        if (matches === null) {
            return terms;
        }

        for (const token of matches) {
            let operator;
            const parts = token.split(":");
            if (token.startsWith('"') || parts.length === 1) {
                // Looks like a normal search term.
                search_term.push(token);
            } else {
                // Looks like an operator.
                negated = false;
                operator = parts.shift();
                // `split` returns a non-empty array
                assert(operator !== undefined);
                if (operator.startsWith("-")) {
                    negated = true;
                    operator = operator.slice(1);
                }
                operand = Filter.decodeOperand(parts.join(":"), operator);

                // Check for user-entered channel name. If the name is valid,
                // convert it to id.
                if (
                    (operator === "channel" || util.is_channel_synonym(operator)) &&
                    Number.isNaN(Number.parseInt(operand, 10))
                ) {
                    const sub = stream_data.get_sub(operand);
                    if (sub) {
                        operand = sub.stream_id.toString();
                    }
                }

                if (
                    for_pills &&
                    operator === "sender" &&
                    operand.toString().toLowerCase() === "me"
                ) {
                    operand = people.my_current_email();
                }

                // We use Filter.operator_to_prefix() to check if the
                // operator is known.  If it is not known, then we treat
                // it as a search for the given string (which may contain
                // a `:`), not as a search operator.
                if (Filter.operator_to_prefix(operator, negated) === "") {
                    // Put it as a search term, to not have duplicate operators
                    search_term.push(token);
                    continue;
                }
                // If any search query was present and it is followed by some other filters
                // then we must add that search filter in its current position in the
                // terms list. This is done so that the last active filter is correctly
                // detected by the `get_search_result` function (in search_suggestions.ts).
                maybe_add_search_terms();
                term = {
                    negated,
                    operator: Filter.canonicalize_operator(operator),
                    operand,
                };
                terms.push(term);
            }
        }

        maybe_add_search_terms();
        return terms;
    }

    static is_valid_search_term(term: NarrowTerm): boolean {
        switch (term.operator) {
            case "has":
                return ["image", "link", "attachment", "reaction"].includes(term.operand);
            case "is":
                return [
                    "dm",
                    "private",
                    "starred",
                    "mentioned",
                    "alerted",
                    "unread",
                    "resolved",
                    "followed",
                    "muted",
                ].includes(term.operand);
            case "in":
                return ["home", "all"].includes(term.operand);
            case "id":
            case "near":
            case "with":
                return Number.isInteger(Number(term.operand));
            case "channel":
            case "stream":
                return stream_data.get_sub_by_id_string(term.operand) !== undefined;
            case "channels":
            case "streams":
                return term.operand === "public";
            case "topic":
                return true;
            case "sender":
            case "from":
            case "dm":
            case "pm":
            case "pm-with":
            case "dm-including":
            case "pm-including":
                if (term.operand === "me") {
                    return true;
                }
                return term.operand
                    .split(",")
                    .every((email) => people.get_by_email(email) !== undefined);
            case "search":
                return true;
            default:
                blueslip.error("Unexpected search term operator: " + term.operator);
                return false;
        }
    }

    /* Convert a list of search terms to a string.
   Each operator is a key-value pair like

       ['topic', 'my amazing topic']

   These are not keys in a JavaScript object, because we
   might need to support multiple terms of the same type.
*/
    static unparse(search_terms: NarrowTerm[]): string {
        const term_strings = search_terms.map((term) => {
            if (term.operator === "search") {
                // Search terms are the catch-all case.
                // All tokens that don't start with a known operator and
                // a colon are glued together to form a search term.
                return term.operand;
            }
            const sign = term.negated ? "-" : "";
            if (term.operator === "") {
                return term.operand;
            }
            const operator = Filter.canonicalize_operator(term.operator);
            return (
                sign + operator + ":" + Filter.encodeOperand(term.operand.toString(), term.operator)
            );
        });
        return term_strings.join(" ");
    }

    static term_type(term: NarrowTerm): string {
        const operator = term.operator;
        const operand = term.operand;
        const negated = term.negated;

        let result = negated ? "not-" : "";

        result += operator;

        if (["is", "has", "in", "channels"].includes(operator)) {
            result += "-" + operand;
        }

        return result;
    }

    static sorted_term_types(term_types: string[]): string[] {
        const levels = [
            "in",
            "channels-public",
            "channel",
            "topic",
            "dm",
            "dm-including",
            "with",
            "sender",
            "near",
            "id",
            "is-alerted",
            "is-mentioned",
            "is-dm",
            "is-starred",
            "is-unread",
            "is-resolved",
            "is-followed",
            "is-muted",
            "has-link",
            "has-image",
            "has-attachment",
            "search",
        ];

        const level = (term_type: string): number => {
            let i = levels.indexOf(term_type);
            if (i === -1) {
                i = 999;
            }
            return i;
        };

        const compare = (a: string, b: string): number => {
            const diff = level(a) - level(b);
            if (diff !== 0) {
                return diff;
            }
            return util.strcmp(a, b);
        };

        return [...term_types].sort(compare);
    }

    static operator_to_prefix(operator: string, negated?: boolean): string {
        operator = Filter.canonicalize_operator(operator);

        if (operator === "search") {
            return negated ? "exclude" : "search for";
        }

        const verb = negated ? "exclude " : "";

        switch (operator) {
            case "channel":
                return verb + "messages in a channel";
            case "channels":
                return verb + "channels";
            case "near":
                return verb + "messages around";

            // Note: We hack around using this in "describe" below.
            case "has":
                return verb + "messages with";

            case "id":
                return verb + "message ID";

            case "topic":
                return verb + "topic";

            case "sender":
                return verb + "sent by";

            case "dm":
                return verb + "direct messages with";

            case "dm-including":
                return verb + "direct messages including";

            case "in":
                return verb + "messages in";

            // Note: We hack around using this in "describe" below.
            case "is":
                return verb + "messages that are";
        }
        return "";
    }

    // Convert a list of terms to a human-readable description.
    static parts_for_describe(terms: NarrowTerm[], is_operator_suggestion: boolean): Part[] {
        const parts: Part[] = [];

        if (terms.length === 0) {
            parts.push({type: "plain_text", content: "combined feed"});
            return parts;
        }

        if (terms[0] !== undefined && terms[1] !== undefined) {
            const is = (term: NarrowTerm, expected: string): boolean =>
                Filter.canonicalize_operator(term.operator) === expected && !term.negated;

            if (is(terms[0], "channel") && is(terms[1], "topic")) {
                // `channel` might be undefined if it's coming from a text query
                const channel = stream_data.get_sub_by_id_string(terms[0].operand)?.name;
                if (channel) {
                    const topic = terms[1].operand;
                    parts.push({
                        type: "channel_topic",
                        channel,
                        topic_display_name: util.get_final_topic_display_name(topic),
                        is_empty_string_topic: topic === "",
                    });
                    terms = terms.slice(2);
                }
            }
        }

        const more_parts = terms.map((term): Part => {
            const operand = term.operand;
            const canonicalized_operator = Filter.canonicalize_operator(term.operator);
            if (canonicalized_operator === "is") {
                // Some operands have their own negative words, like
                // unresolved, rather than the default "exclude " prefix.
                const custom_negated_operand_phrases: Record<string, string> = {
                    resolved: "unresolved",
                };
                const negated_phrase = custom_negated_operand_phrases[operand];
                if (term.negated && negated_phrase !== undefined) {
                    return {
                        type: "is_operator",
                        verb: "",
                        operand: negated_phrase,
                    };
                }

                const verb = term.negated ? "exclude " : "";
                return {
                    type: "is_operator",
                    verb,
                    operand,
                };
            }
            if (canonicalized_operator === "has") {
                // search_suggestion.get_suggestions takes care that this message will
                // only be shown if the `has` operator is not at the last.
                const valid_has_operands = [
                    "image",
                    "images",
                    "link",
                    "links",
                    "attachment",
                    "attachments",
                    "reaction",
                    "reactions",
                ];
                if (!valid_has_operands.includes(operand)) {
                    return {
                        type: "invalid_has",
                        operand,
                    };
                }
            }
            if (canonicalized_operator === "channels" && operand === "public") {
                return {
                    type: "plain_text",
                    content: this.describe_public_channels(term.negated ?? false),
                };
            }
            const prefix_for_operator = Filter.operator_to_prefix(
                canonicalized_operator,
                term.negated,
            );
            if (USER_OPERATORS.has(canonicalized_operator)) {
                const user_emails = operand.split(",");
                const users: ValidOrInvalidUser[] = user_emails.map((email) => {
                    const person = people.get_by_email(email);
                    if (person === undefined) {
                        return {
                            valid_user: false,
                            operand: email,
                        };
                    }
                    return {
                        valid_user: true,
                        user_pill_context: create_user_pill_context(person),
                    };
                });
                return {
                    type: "user_pill",
                    operator: prefix_for_operator,
                    users,
                };
            }
            if (prefix_for_operator !== "") {
                if (canonicalized_operator === "channel") {
                    const stream = stream_data.get_sub_by_id_string(operand);
                    const verb = term.negated ? "exclude " : "";
                    if (stream) {
                        return {
                            type: "channel",
                            prefix_for_operator: verb + "messages in #",
                            operand: stream.name,
                        };
                    }
                    // Assume the operand is a partially formed name and return
                    // the operator as the channel name in the next block.
                }
                if (canonicalized_operator === "topic" && !is_operator_suggestion) {
                    return {
                        type: "prefix_for_operator",
                        prefix_for_operator,
                        operand: util.get_final_topic_display_name(operand),
                        is_empty_string_topic: operand === "",
                    };
                }
                return {
                    type: "prefix_for_operator",
                    prefix_for_operator,
                    operand,
                };
            }
            return {
                type: "plain_text",
                content: "unknown operator",
            };
        });
        return [...parts, ...more_parts];
    }

    static describe_public_channels(negated: boolean): string {
        const possible_prefix = negated ? "exclude " : "";
        if (page_params.is_spectator || current_user.is_guest) {
            return possible_prefix + "all public channels that you can view";
        }
        return possible_prefix + "all public channels";
    }

    static search_description_as_html(
        terms: NarrowTerm[],
        is_operator_suggestion: boolean,
    ): string {
        return render_search_description({
            parts: Filter.parts_for_describe(terms, is_operator_suggestion),
        });
    }

    static is_spectator_compatible(terms: NarrowTerm[]): boolean {
        for (const term of terms) {
            if (term.operand === undefined) {
                return false;
            }
            if (!hash_parser.is_an_allowed_web_public_narrow(term.operator, term.operand)) {
                return false;
            }
        }
        return true;
    }

    static adjusted_terms_if_moved(raw_terms: NarrowTerm[], message: Message): NarrowTerm[] | null {
        // In case of narrow containing non-channel messages, we replace the
        // channel/topic/dm operators with singular dm operator corresponding
        // to the message if it contains `with` operator.
        if (message.type !== "stream") {
            const contains_with_operator = raw_terms.some((term) => term.operator === "with");

            if (!contains_with_operator) {
                return null;
            }
            const conversation_terms = new Set(["channel", "topic", "dm"]);
            const filtered_terms = raw_terms.filter((term) => {
                const operator = Filter.canonicalize_operator(term.operator);
                return !conversation_terms.has(operator);
            });

            assert(typeof message.display_recipient !== "string");

            // We should make sure the current user is not included for
            // the `dm` operand for the narrow.
            const dm_participants = message.display_recipient
                .map((user) => user.email)
                .filter((user_email) => user_email !== current_user.email);

            // However, if the current user is the only recipient of the
            // message, we should include the user in the operand.
            if (dm_participants.length === 0) {
                dm_participants.push(current_user.email);
            }

            const dm_operand = dm_participants.join(",");

            const dm_conversation_terms = [{operator: "dm", operand: dm_operand, negated: false}];
            return [...dm_conversation_terms, ...filtered_terms];
        }

        assert(typeof message.display_recipient === "string");
        assert(typeof message.topic === "string");

        const adjusted_terms = [];
        let terms_changed = false;

        const adjusted_narrow_containing_with = Filter.ensure_channel_topic_terms(
            raw_terms,
            message,
        );

        if (adjusted_narrow_containing_with !== undefined) {
            return adjusted_narrow_containing_with;
        }

        for (const term of raw_terms) {
            const adjusted_term = {...term};
            if (
                Filter.canonicalize_operator(term.operator) === "channel" &&
                term.operand !== message.stream_id.toString()
            ) {
                adjusted_term.operand = message.stream_id.toString();
                terms_changed = true;
            }
            if (
                Filter.canonicalize_operator(term.operator) === "topic" &&
                !util.lower_same(term.operand, message.topic)
            ) {
                adjusted_term.operand = message.topic;
                terms_changed = true;
            }

            adjusted_terms.push(adjusted_term);
        }

        if (!terms_changed) {
            return null;
        }

        return adjusted_terms;
    }

    setup_filter(terms: NarrowTerm[]): void {
        this._terms = this.fix_terms(terms);
        this.cached_sorted_terms_for_comparison = undefined;
    }

    equals(filter: Filter, excluded_operators?: string[]): boolean {
        return _.isEqual(
            filter.sorted_terms_for_comparison(excluded_operators),
            this.sorted_terms_for_comparison(excluded_operators),
        );
    }

    sorted_terms_for_comparison(excluded_operators?: string[]): string[] {
        if (!excluded_operators && this.cached_sorted_terms_for_comparison !== undefined) {
            return this.cached_sorted_terms_for_comparison;
        }

        let filter_terms = this._terms;
        if (excluded_operators) {
            filter_terms = this._terms.filter(
                (term) => !excluded_operators.includes(term.operator),
            );
        }

        const sorted_simplified_terms = filter_terms
            .map((term) => {
                let operand = term.operand;
                if (term.operator === "channel" || term.operator === "topic") {
                    operand = operand.toLowerCase();
                }

                return `${term.negated ? "0" : "1"}-${term.operator}-${operand}`;
            })
            .sort(util.strcmp);

        if (!excluded_operators) {
            this.cached_sorted_terms_for_comparison = sorted_simplified_terms;
        }

        return sorted_simplified_terms;
    }

    predicate(): (message: Message) => boolean {
        this._predicate ??= this._build_predicate();
        return this._predicate;
    }

    terms(): NarrowTerm[] {
        return this._terms;
    }

    public_terms(): NarrowTerm[] {
        const safe_to_return = this._terms.filter(
            // Filter out the embedded narrow (if any).
            (term) => {
                // TODO(stream_id): Ideally we have `page_params.narrow_stream_id`
                if (page_params.narrow_stream === undefined || term.operator !== "channel") {
                    return true;
                }
                const narrow_stream = stream_data.get_sub_by_name(page_params.narrow_stream);
                assert(narrow_stream !== undefined);
                return Number.parseInt(term.operand, 10) === narrow_stream.stream_id;
            },
        );
        return safe_to_return;
    }

    operands(operator: string): string[] {
        return this._terms
            .filter((term) => !term.negated && term.operator === operator)
            .map((term) => term.operand);
    }

    has_negated_operand(operator: string, operand: string): boolean {
        return this._terms.some(
            (term) => term.negated && term.operator === operator && term.operand === operand,
        );
    }

    has_operand_case_insensitive(operator: string, operand: string): boolean {
        return this._terms.some(
            (term) =>
                !term.negated &&
                term.operator === operator &&
                term.operand.toLowerCase() === operand.toLowerCase(),
        );
    }

    has_operand(operator: string, operand: string): boolean {
        return this._terms.some(
            (term) => !term.negated && term.operator === operator && term.operand === operand,
        );
    }

    has_operator(operator: string): boolean {
        return this._terms.some((term) => {
            if (term.negated && !["search", "has"].includes(term.operator)) {
                return false;
            }
            return term.operator === operator;
        });
    }

    is_in_home(): boolean {
        // Combined feed view
        return (
            // The `-is:muted` term is an alias for `in:home`. The `in:home` term will
            // be removed in the future.
            this._terms.length === 1 &&
            (this.has_operand("in", "home") || this.has_negated_operand("is", "muted"))
        );
    }

    has_exactly_channel_topic_operators(): boolean {
        if (
            this.terms().length === 2 &&
            this.has_operator("channel") &&
            this.has_operator("topic")
        ) {
            return true;
        }
        return false;
    }

    is_keyword_search(): boolean {
        return this.has_operator("search");
    }

    is_non_group_direct_message(): boolean {
        return this.has_operator("dm") && this.operands("dm")[0]!.split(",").length === 1;
    }

    contains_no_partial_conversations(): boolean {
        // Determines whether a view is guaranteed, by construction,
        // to contain consecutive messages in a given topic, and thus
        // it is appropriate to collapse recipient/sender headings.
        const term_types = this.sorted_term_types();

        // All search/narrow term types, including negations, with the
        // property that if a message is in the view, then any other
        // message sharing its recipient (channel/topic or direct
        // message recipient) must also be present in the view.
        const valid_term_types = new Set([
            "channel",
            "not-channel",
            "topic",
            "not-topic",
            "dm",
            "dm-including",
            "not-dm-including",
            "is-dm",
            "not-is-dm",
            "is-resolved",
            "not-is-resolved",
            "is-followed",
            "not-is-followed",
            "is-muted",
            "not-is-muted",
            "in-home",
            "in-all",
            "channels-public",
            "not-channels-public",
            "channels-web-public",
            "not-channels-web-public",
            "near",
            "with",
        ]);

        for (const term of term_types) {
            if (!valid_term_types.has(term)) {
                return false;
            }
        }
        return true;
    }

    calc_can_mark_messages_read(): boolean {
        // Arguably this should match contains_no_partial_conversations.
        // We may want to standardize on that in the future.  (At
        // present, this function does not allow combining valid filters).
        if (this.single_term_type_returns_all_messages_of_conversation()) {
            return true;
        }
        return false;
    }

    can_mark_messages_read(): boolean {
        this._can_mark_messages_read ??= this.calc_can_mark_messages_read();
        return this._can_mark_messages_read;
    }

    single_term_type_returns_all_messages_of_conversation(): boolean {
        const term_types = this.sorted_term_types();

        // "topic" alone cannot guarantee all messages of a conversation because
        // it is limited by the user's message history. Therefore, we check "channel"
        // and "topic" together to ensure that the current filter will return all the
        // messages of a conversation.
        if (_.isEqual(term_types, ["channel", "topic", "with"])) {
            return true;
        }

        if (_.isEqual(term_types, ["channel", "topic"])) {
            return true;
        }

        if (_.isEqual(term_types, ["dm", "with"])) {
            return true;
        }

        if (_.isEqual(term_types, ["dm"])) {
            return true;
        }

        if (_.isEqual(term_types, ["channel"])) {
            return true;
        }

        if (_.isEqual(term_types, ["is-dm"])) {
            return true;
        }

        if (_.isEqual(term_types, ["not-is-dm"])) {
            return true;
        }

        if (_.isEqual(term_types, ["is-resolved"])) {
            return true;
        }

        if (_.isEqual(term_types, ["in-home"])) {
            return true;
        }

        if (_.isEqual(term_types, ["not-is-muted"])) {
            return true;
        }

        if (_.isEqual(term_types, ["in-all"])) {
            return true;
        }

        if (_.isEqual(term_types, [])) {
            // Empty filters means we are displaying all possible messages.
            return true;
        }

        return false;
    }

    // This is used to control the behaviour for "exiting search",
    // given the ability to flip between displaying the search bar and the narrow description in UI
    // here we define a narrow as a "common narrow" on the basis of
    // https://paper.dropbox.com/doc/Navbar-behavior-table--AvnMKN4ogj3k2YF5jTbOiVv_AQ-cNOGtu7kSdtnKBizKXJge
    // common narrows show a narrow description and allow the user to
    // close search bar UI and show the narrow description UI.
    is_common_narrow(): boolean {
        if (this.single_term_type_returns_all_messages_of_conversation()) {
            return true;
        }
        const term_types = this.sorted_term_types();
        if (_.isEqual(term_types, ["is-mentioned"])) {
            return true;
        }
        if (_.isEqual(term_types, ["is-starred"])) {
            return true;
        }
        if (_.isEqual(term_types, ["channels-public"])) {
            return true;
        }
        if (_.isEqual(term_types, ["sender"])) {
            return true;
        }
        if (_.isEqual(term_types, ["is-followed"])) {
            return true;
        }
        if (
            _.isEqual(term_types, ["sender", "has-reaction"]) &&
            this.operands("sender")[0] === people.my_current_email()
        ) {
            return true;
        }
        return false;
    }

    // This is used to control the behaviour for "exiting search"
    // within a narrow (E.g. a channel/topic + search) to bring you to
    // the containing common narrow (channel/topic, in the example)
    // rather than the "Combined feed" view.
    //
    // Note from tabbott: The slug-based approach may not be ideal; we
    // may be able to do better another way.
    generate_redirect_url(): string {
        const term_types = this.sorted_term_types();

        // this comes first because it has 3 term_types but is not a "complex filter"
        if (
            _.isEqual(term_types, ["sender", "search", "has-reaction"]) &&
            this.operands("sender")[0] === people.my_current_email()
        ) {
            return "/#narrow/has/reaction/sender/me";
        }
        if (_.isEqual(term_types, ["channel", "topic", "search"])) {
            const sub = stream_data.get_sub_by_id_string(this.operands("channel")[0]!);
            // if channel does not exist, redirect to home view
            if (!sub) {
                return "#";
            }
            return (
                "/#narrow/channel/" +
                stream_data.id_to_slug(sub.stream_id) +
                "/topic/" +
                this.operands("topic")[0]
            );
        }

        // eliminate "complex filters"
        if (term_types.length >= 3) {
            return "#"; // redirect to All
        }

        if (term_types[1] === "search") {
            switch (term_types[0]) {
                case "channel": {
                    const sub = stream_data.get_sub_by_id_string(this.operands("channel")[0]!);
                    // if channel does not exist, redirect to home view
                    if (!sub) {
                        return "#";
                    }
                    return "/#narrow/channel/" + stream_data.id_to_slug(sub.stream_id);
                }
                case "is-dm":
                    return "/#narrow/is/dm";
                case "is-starred":
                    return "/#narrow/is/starred";
                case "is-mentioned":
                    return "/#narrow/is/mentioned";
                case "channels-public":
                    return "/#narrow/channels/public";
                case "dm":
                    return "/#narrow/dm/" + people.emails_to_slug(this.operands("dm").join(","));
                case "is-resolved":
                    return "/#narrow/topics/is/resolved";
                case "is-followed":
                    return "/#narrow/topics/is/followed";
                // TODO: It is ambiguous how we want to handle the 'sender' case,
                // we may remove it in the future based on design decisions
                case "sender":
                    return "/#narrow/sender/" + people.emails_to_slug(this.operands("sender")[0]!);
            }
        }

        return "#"; // redirect to All
    }

    add_icon_data(context: {
        title?: string;
        html_title?: string;
        description?: string | undefined;
        link?: string | undefined;
        is_spectator: boolean;
    }): IconData {
        // We have special icons for the simple narrows available for the via sidebars.
        const term_types = this.sorted_term_types();
        let icon;
        let zulip_icon;

        if (
            _.isEqual(term_types, ["sender", "has-reaction"]) &&
            this.operands("sender")[0] === people.my_current_email()
        ) {
            zulip_icon = "smile";
            return {...context, zulip_icon};
        }

        switch (term_types[0]) {
            case "in-home":
            case "in-all":
                icon = "home";
                break;
            case "channel": {
                const sub = stream_data.get_sub_by_id_string(this.operands("channel")[0]!);
                if (!sub) {
                    icon = "question-circle-o";
                    break;
                }
                if (sub.is_archived) {
                    zulip_icon = "archive";
                    break;
                }
                if (sub.invite_only) {
                    zulip_icon = "lock";
                    break;
                }
                if (sub.is_web_public) {
                    zulip_icon = "globe";
                    break;
                }
                zulip_icon = "hashtag";
                break;
            }
            case "is-dm":
                zulip_icon = "user";
                break;
            case "is-starred":
                zulip_icon = "star";
                break;
            case "is-mentioned":
                zulip_icon = "at-sign";
                break;
            case "dm":
                zulip_icon = "user";
                break;
            case "is-resolved":
                icon = "check";
                break;
            case "is-followed":
                zulip_icon = "follow";
                break;
            default:
                icon = undefined;
                break;
        }
        if (zulip_icon) {
            return {...context, zulip_icon};
        }
        return {...context, icon};
    }

    get_title(): string | undefined {
        // Nice explanatory titles for common views.
        const term_types = this.sorted_term_types();
        if (
            (term_types.length === 3 && _.isEqual(term_types, ["channel", "topic", "near"])) ||
            (term_types.length === 3 && _.isEqual(term_types, ["channel", "topic", "with"])) ||
            (term_types.length === 2 && _.isEqual(term_types, ["channel", "topic"])) ||
            (term_types.length === 1 && _.isEqual(term_types, ["channel"]))
        ) {
            const sub = stream_data.get_sub_by_id_string(this.operands("channel")[0]!);
            if (!sub) {
                return $t({defaultMessage: "Unknown channel"});
            }
            return sub.name;
        }
        if (
            (term_types.length === 2 && _.isEqual(term_types, ["dm", "near"])) ||
            (term_types.length === 2 && _.isEqual(term_types, ["dm", "with"])) ||
            (term_types.length === 1 && _.isEqual(term_types, ["dm"]))
        ) {
            const emails = this.operands("dm")[0]!.split(",");
            if (emails.length === 1) {
                const user = people.get_by_email(emails[0]!);
                if (user && people.is_direct_message_conversation_with_self([user.user_id])) {
                    return $t({defaultMessage: "Messages with yourself"});
                }
            }
            const names = emails.map((email) => {
                const person = people.get_by_email(email);
                if (!person) {
                    return email;
                }
                if (muted_users.is_user_muted(person.user_id)) {
                    if (people.should_add_guest_user_indicator(person.user_id)) {
                        return $t({defaultMessage: "Muted user (guest)"});
                    }

                    return $t({defaultMessage: "Muted user"});
                }
                if (people.should_add_guest_user_indicator(person.user_id)) {
                    return $t({defaultMessage: "{name} (guest)"}, {name: person.full_name});
                }
                return person.full_name;
            });
            names.sort(util.make_strcmp());
            return util.format_array_as_list(names, "long", "conjunction");
        }
        if (term_types.length === 1 && _.isEqual(term_types, ["sender"])) {
            const email = this.operands("sender")[0]!;
            const user = people.get_by_email(email);
            let sender = email;
            if (user) {
                if (people.is_my_user_id(user.user_id)) {
                    return $t({defaultMessage: "Messages sent by you"});
                }

                if (people.should_add_guest_user_indicator(user.user_id)) {
                    sender = $t({defaultMessage: "{name} (guest)"}, {name: user.full_name});
                } else {
                    sender = user.full_name;
                }
            }

            return $t(
                {defaultMessage: "Messages sent by {sender}"},
                {
                    sender,
                },
            );
        }
        if (term_types.length === 1) {
            switch (term_types[0]) {
                case "in-home":
                    return $t({defaultMessage: "Combined feed"});
                case "in-all":
                    return $t({defaultMessage: "All messages including muted channels"});
                case "channels-public":
                    if (page_params.is_spectator || current_user.is_guest) {
                        return $t({
                            defaultMessage: "Messages in all public channels that you can view",
                        });
                    }
                    return $t({defaultMessage: "Messages in all public channels"});
                case "is-starred":
                    return $t({defaultMessage: "Starred messages"});
                case "is-mentioned":
                    return $t({defaultMessage: "Mentions"});
                case "is-dm":
                    return $t({defaultMessage: "Direct message feed"});
                case "is-resolved":
                    return $t({defaultMessage: "Resolved topics"});
                case "is-followed":
                    return $t({defaultMessage: "Followed topics"});
                // These cases return false for is_common_narrow, and therefore are not
                // formatted in the message view header. They are used in narrow.js to
                // update the browser title.
                case "is-alerted":
                    return $t({defaultMessage: "Alerted messages"});
                case "is-unread":
                    return $t({defaultMessage: "Unread messages"});
            }
        }
        if (
            _.isEqual(term_types, ["sender", "has-reaction"]) &&
            this.operands("sender")[0] === people.my_current_email()
        ) {
            return $t({defaultMessage: "Reactions"});
        }
        /* istanbul ignore next */
        return undefined;
    }

    get_description(): {description: string; link: string} | undefined {
        const term_types = this.sorted_term_types();
        switch (term_types[0]) {
            case "is-mentioned":
                return {
                    description: $t({defaultMessage: "Messages where you are mentioned."}),
                    link: "/help/view-your-mentions",
                };
            case "is-starred":
                return {
                    description: $t({
                        defaultMessage: "Important messages, tasks, and other useful references.",
                    }),
                    link: "/help/star-a-message#view-your-starred-messages",
                };
            case "is-followed":
                return {
                    description: $t({
                        defaultMessage: "Messages in topics you follow.",
                    }),
                    link: "/help/follow-a-topic",
                };
        }
        if (
            _.isEqual(term_types, ["sender", "has-reaction"]) &&
            this.operands("sender")[0] === people.my_current_email()
        ) {
            return {
                description: $t({
                    defaultMessage: "Emoji reactions to your messages.",
                }),
                link: "/help/emoji-reactions",
            };
        }
        return undefined;
    }

    allow_use_first_unread_when_narrowing(): boolean {
        return (
            this.can_mark_messages_read() ||
            (this.has_operator("is") && !this.has_operand("is", "starred"))
        );
    }

    contains_only_private_messages(): boolean {
        return (
            (this.has_operator("is") && this.operands("is")[0] === "dm") ||
            this.has_operator("dm") ||
            this.has_operator("dm-including")
        );
    }

    includes_full_stream_history(): boolean {
        return this.has_operator("channel") || this.has_operator("channels");
    }

    is_personal_filter(): boolean {
        // Whether the filter filters for user-specific data in the
        // UserMessage table, such as stars or mentions.
        //
        // Such filters should not advertise "channels:public" as it
        // will never add additional results.
        // NOTE: Needs to be in sync with `zerver.lib.narrow.ok_to_include_history`.
        return this.has_operator("is") && !this.has_operand("is", "resolved");
    }

    can_apply_locally(is_local_echo = false): boolean {
        // Since there can be multiple operators, each block should
        // just return false here.

        if (this.is_keyword_search()) {
            // The semantics for matching keywords are implemented
            // by database plugins, and we don't have JS code for
            // that, plus search queries tend to go too far back in
            // history.
            return false;
        }

        if (this.has_operator("has") && is_local_echo) {
            // The has: operators can be applied locally for messages
            // rendered by the backend; links, attachments, and images
            // are not handled properly by the local echo Markdown
            // processor.
            return false;
        }

        // TODO: It's not clear why `channels:` filters would not be
        // applicable locally.
        if (this.has_operator("channels") || this.has_negated_operand("channels", "public")) {
            return false;
        }

        // If we get this far, we're good!
        return true;
    }

    fix_terms(terms: NarrowTerm[]): NarrowTerm[] {
        terms = this._canonicalize_terms(terms);
        terms = this._fix_redundant_is_private(terms);
        return terms;
    }

    _fix_redundant_is_private(terms: NarrowTerm[]): NarrowTerm[] {
        // Every DM is a DM, so drop `is:dm` if on a DM conversation.
        if (!terms.some((term) => Filter.term_type(term) === "dm")) {
            return terms;
        }

        return terms.filter((term) => Filter.term_type(term) !== "is-dm");
    }

    _canonicalize_terms(terms_mixed_case: NarrowTerm[]): NarrowTerm[] {
        return terms_mixed_case.map((term: NarrowTerm) => Filter.canonicalize_term(term));
    }

    adjust_with_operand_to_message(msg_id: number): void {
        const narrow_terms = this._terms.filter((term) => term.operator !== "with");
        const adjusted_with_term = {operator: "with", operand: `${msg_id}`};
        const adjusted_terms = [...narrow_terms, adjusted_with_term];
        this._terms = adjusted_terms;
        this.requires_adjustment_for_moved_with_target = false;
    }

    filter_with_new_params(params: NarrowTerm): Filter {
        const new_params = this.fix_terms([params])[0];
        assert(new_params !== undefined);
        const terms = this._terms.map((term) => {
            const new_term = {...term};
            if (new_term.operator === new_params.operator && !new_term.negated) {
                new_term.operand = new_params.operand;
            }
            return new_term;
        });
        return new Filter(terms);
    }

    has_topic(stream_id: number, topic: string): boolean {
        return (
            this.has_operand("channel", stream_id.toString()) && this.has_operand("topic", topic)
        );
    }

    sorted_term_types(): string[] {
        // We need to rebuild the sorted_term_types if at all our narrow
        // is updated (through `with` operator).
        if (this._sorted_term_types === undefined || this.narrow_requires_hash_change) {
            this._sorted_term_types = this._build_sorted_term_types();
        }
        return this._sorted_term_types;
    }

    _build_sorted_term_types(): string[] {
        const terms = this._terms;
        const term_types = terms.map((term) => Filter.term_type(term));
        const sorted_terms = Filter.sorted_term_types(term_types);
        return sorted_terms;
    }

    can_bucket_by(...wanted_term_types: string[]): boolean {
        // Examples call:
        //     filter.can_bucket_by('channel', 'topic')
        //
        // The use case of this function is that we want
        // to know if a filter can start with a bucketing
        // data structure similar to the ones we have in
        // unread.ts to pre-filter ids, rather than apply
        // a predicate to a larger list of candidate ids.
        //
        // (It's for optimization, basically.)
        const all_term_types = this.sorted_term_types();
        const term_types = all_term_types.slice(0, wanted_term_types.length);

        return _.isEqual(term_types, wanted_term_types);
    }

    first_valid_id_from(msg_ids: number[]): number | undefined {
        const predicate = this.predicate();

        const first_id = msg_ids.find((msg_id) => {
            const message = message_store.get(msg_id);

            if (message === undefined) {
                return false;
            }

            return predicate(message);
        });

        return first_id;
    }

    update_email(user_id: number, new_email: string): void {
        for (const term of this._terms) {
            switch (term.operator) {
                case "dm-including":
                case "group-pm-with":
                case "dm":
                case "pm-with":
                case "sender":
                case "from":
                    term.operand = people.update_email_in_reply_to(
                        term.operand,
                        user_id,
                        new_email,
                    );
            }
        }
    }

    // Build a filter function from a list of operators.
    _build_predicate(): (message: Message) => boolean {
        const terms = this._terms;

        if (!this.can_apply_locally()) {
            return () => true;
        }

        // FIXME: This is probably pretty slow.
        // We could turn it into something more like a compiler:
        // build JavaScript code in a string and then eval() it.

        return (message: Message) =>
            terms.every((term) => {
                let ok = message_matches_search_term(message, term.operator, term.operand);
                if (term.negated) {
                    ok = !ok;
                }
                return ok;
            });
    }

    can_show_next_unread_topic_conversation_button(): boolean {
        const term_types = this.sorted_term_types();
        if (
            _.isEqual(term_types, ["channel", "topic", "near"]) ||
            _.isEqual(term_types, ["channel", "topic", "with"]) ||
            _.isEqual(term_types, ["channel", "topic"]) ||
            _.isEqual(term_types, ["channel"])
        ) {
            return true;
        }
        return false;
    }

    can_show_next_unread_dm_conversation_button(): boolean {
        const term_types = this.sorted_term_types();
        if (
            _.isEqual(term_types, ["dm", "near"]) ||
            _.isEqual(term_types, ["dm", "with"]) ||
            _.isEqual(term_types, ["dm"]) ||
            _.isEqual(term_types, ["is-dm"])
        ) {
            return true;
        }
        return false;
    }

    is_conversation_view(): boolean {
        const term_types = this.sorted_term_types();
        if (
            _.isEqual(term_types, ["channel", "topic", "with"]) ||
            _.isEqual(term_types, ["channel", "topic"]) ||
            _.isEqual(term_types, ["dm", "with"]) ||
            _.isEqual(term_types, ["dm"])
        ) {
            return true;
        }
        return false;
    }

    is_conversation_view_with_near(): boolean {
        const term_types = this.sorted_term_types();
        if (
            _.isEqual(term_types, ["channel", "topic", "near"]) ||
            _.isEqual(term_types, ["dm", "near"])
        ) {
            return true;
        }
        return false;
    }

    is_channel_view(): boolean {
        return (
            this._terms.length === 1 &&
            this._terms[0] !== undefined &&
            Filter.term_type(this._terms[0]) === "channel"
        );
    }

    may_contain_multiple_conversations(): boolean {
        return !(
            (this.has_operator("channel") && this.has_operator("topic")) ||
            this.has_operator("dm")
        );
    }

    excludes_muted_topics(): boolean {
        return (
            // not narrowed to a topic
            !(this.has_operator("channel") && this.has_operator("topic")) &&
            // not narrowed to search
            !this.is_keyword_search() &&
            // not narrowed to dms
            !(this.has_operator("dm") || this.has_operand("is", "dm")) &&
            // not narrowed to starred messages
            !this.has_operand("is", "starred") &&
            // not narrowed to negated home messages
            !this.has_negated_operand("in", "home") &&
            // not narrowed to muted topics messages
            !this.has_operand("is", "muted")
        );
    }

    try_adjusting_for_moved_with_target(message?: Message): void {
        // If we have the message named in a `with` operator
        // available, either via parameter or message_store,
        if (!this.requires_adjustment_for_moved_with_target) {
            return;
        }

        if (!message) {
            const message_id = Number.parseInt(this.operands("with")[0]!, 10);
            message = message_store.get(message_id);
        }

        if (!message) {
            return;
        }

        const adjusted_terms = Filter.adjusted_terms_if_moved(this._terms, message);
        if (adjusted_terms) {
            // If the narrow terms are adjusted, then we need to update the
            // hash user entered, to point to the updated narrow.
            this.narrow_requires_hash_change = true;
            this.setup_filter(adjusted_terms);
        }
        this.requires_adjustment_for_moved_with_target = false;
    }

    can_newly_match_moved_messages(new_channel_id: string, new_topic: string): boolean {
        // Checks if any of the operators on this Filter object have
        // the property that it's possible for their true value to
        // change as a result of messages being moved into the
        // channel/topic pair provided in the parameters.
        if (this.has_operand_case_insensitive("channel", new_channel_id)) {
            return true;
        }

        if (this.has_operand_case_insensitive("topic", new_topic)) {
            return true;
        }

        const term_types = this.sorted_term_types();
        const can_match_moved_msg_term_types = new Set([
            // For some of these operators, we could return `false`
            // with more analysis of either the pre-move location,
            // user_topic metadata, etc.
            //
            // It might be worth the effort for the more common views,
            // such as the Combined Feed, but some of these operators
            // are very unlikely to be used in practice.
            "not-channel",
            "not-topic",
            "is-followed",
            "not-is-followed",
            "is-resolved",
            "not-is-resolved",
            "channels-public",
            "not-channels-public",
            "is-muted",
            "not-is-muted",
            "in-home",
            "not-in-home",
            "in-all",
            "not-in-all",
            "search",
        ]);

        for (const term of term_types) {
            if (can_match_moved_msg_term_types.has(term)) {
                return true;
            }
        }

        return false;
    }

    get_stringified_narrow_for_server_query(): string {
        return JSON.stringify(
            this._terms.map((term) => {
                if (term.operator === "channel") {
                    return {
                        ...term,
                        operand: Number.parseInt(term.operand, 10),
                    };
                }
                return term;
            }),
        );
    }
}
