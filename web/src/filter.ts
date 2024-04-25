import _ from "lodash";
import assert from "minimalistic-assert";

import * as resolved_topic from "../shared/src/resolved_topic";
import render_search_description from "../templates/search_description.hbs";

import * as hash_parser from "./hash_parser";
import {$t} from "./i18n";
import * as message_parser from "./message_parser";
import * as message_store from "./message_store";
import type {Message} from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import {realm} from "./state_data";
import type {NarrowTerm} from "./state_data";
import * as stream_data from "./stream_data";
import type {StreamSubscription} from "./sub_store";
import * as unread from "./unread";
import * as user_topics from "./user_topics";
import * as util from "./util";

type IconData = {
    title: string;
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
          topic: string;
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
      };

// TODO: When "stream" is renamed to "channel", these placeholders
// should be removed, or replaced with helper functions similar
// to util.is_topic_synonym.
const CHANNEL_SYNONYM = "stream";
const CHANNELS_SYNONYM = "streams";

function zephyr_stream_name_match(message: Message & {type: "stream"}, operand: string): boolean {
    // Zephyr users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
    // (unsocial, ununsocial, social.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(?:un)*(.+?)(?:\.d)*$/i.exec(operand);
    let base_stream_name = operand;
    if (m?.[1] !== undefined) {
        base_stream_name = m[1];
    }
    const related_regexp = new RegExp(
        /^(un)*/.source + _.escapeRegExp(base_stream_name) + /(\.d)*$/.source,
        "i",
    );
    const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    return related_regexp.test(stream_name);
}

function zephyr_topic_name_match(message: Message & {type: "stream"}, operand: string): boolean {
    // Zephyr users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
    // (foo, foo.d, foo.d.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(.*?)(?:\.d)*$/i.exec(operand);
    // m should never be null because any string matches that regex.
    assert(m !== null);
    const base_topic = m[1];
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
    // with additional logic for unmuted topics, mentions, and
    // single-channel windows.
    if (message.type === "private") {
        return true;
    }
    const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    if (
        message.mentioned ||
        (page_params.narrow_stream !== undefined &&
            stream_name.toLowerCase() === page_params.narrow_stream.toLowerCase())
    ) {
        return true;
    }

    return (
        !stream_data.is_muted(message.stream_id) ||
        user_topics.is_topic_unmuted(message.stream_id, message.topic)
    );
}

function message_matches_search_term(message: Message, operator: string, operand: string): boolean {
    switch (operator) {
        case "has":
            switch (operand) {
                case "image":
                    return message_parser.message_has_image(message);
                case "link":
                    return message_parser.message_has_link(message);
                case "attachment":
                    return message_parser.message_has_attachment(message);
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
                    return unread.message_unread(message);
                case "resolved":
                    return message.type === "stream" && resolved_topic.is_resolved(message.topic);
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

            operand = operand.toLowerCase();
            if (realm.realm_is_zephyr_mirror_realm) {
                return zephyr_stream_name_match(message, operand);
            }

            // Try to match by stream_id if have a valid sub for
            // the operand. If we can't find the id, we return false.
            const stream_id = stream_data.get_stream_id(operand);
            return stream_id !== undefined && message.stream_id === stream_id;
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
            const operand_ids = people.pm_with_operand_ids(operand);
            if (!operand_ids) {
                return false;
            }
            const user_ids = people.all_user_ids_in_pm(message);
            if (!user_ids) {
                return false;
            }
            return user_ids.includes(operand_ids[0]);
        }
    }

    return true; // unknown operators return true (effectively ignored)
}

export class Filter {
    _terms: NarrowTerm[];
    _sub?: StreamSubscription;
    _sorted_term_types?: string[] = undefined;
    _predicate?: (message: Message) => boolean;
    _can_mark_messages_read?: boolean;

    constructor(terms: NarrowTerm[]) {
        this._terms = this.fix_terms(terms);
        if (this.has_operator("channel")) {
            this._sub = stream_data.get_sub_by_name(this.operands("channel")[0]);
        }
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

        if (operator === CHANNEL_SYNONYM) {
            return "channel";
        }

        if (operator === CHANNELS_SYNONYM) {
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
                operand = stream_data.get_name(operand);
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
                operand = operand
                    .toString()
                    .toLowerCase()
                    .replaceAll(/[\u201C\u201D]/g, '"');
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

    /* We use a variant of URI encoding which looks reasonably
       nice and still handles unambiguously cases such as
       spaces in operands.

       This is just for the search bar, not for saving the
       narrow in the URL fragment.  There we do use full
       URI encoding to avoid problematic characters. */
    static encodeOperand(operand: string): string {
        return operand
            .replaceAll("%", "%25")
            .replaceAll("+", "%2B")
            .replaceAll(" ", "+")
            .replaceAll('"', "%22");
    }

    static decodeOperand(encoded: string, operator: string): string {
        encoded = encoded.replaceAll('"', "");
        if (
            !["dm-including", "dm", "sender", "from", "pm-with", "group-pm-with"].includes(operator)
        ) {
            encoded = encoded.replaceAll("+", " ");
        }
        return util.robust_url_decode(encoded).trim();
    }

    // Parse a string into a list of terms (see below).
    static parse(str: string): NarrowTerm[] {
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
        // quotes, preceded by an optional operator that may have a space after it.
        // TODO: rewrite this using `str.matchAll` to get out the match objects
        // with individual capture groups, so we don’t need to write a separate
        // parser with `.split`.
        const matches = str.match(/([^\s:]+: ?)?("[^"]+"?|\S+)/g);
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
                term = {negated, operator, operand};
                terms.push(term);
            }
        }

        maybe_add_search_terms();
        return terms;
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
            return sign + operator + ":" + Filter.encodeOperand(term.operand.toString());
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
            "sender",
            "near",
            "id",
            "is-alerted",
            "is-mentioned",
            "is-dm",
            "is-starred",
            "is-unread",
            "is-resolved",
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
                return verb + "channel";
            case "channels":
                return verb + "channels";
            case "near":
                return verb + "messages around";

            // Note: We hack around using this in "describe" below.
            case "has":
                return verb + "messages with one or more";

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
    static parts_for_describe(terms: NarrowTerm[]): Part[] {
        const parts: Part[] = [];

        if (terms.length === 0) {
            parts.push({type: "plain_text", content: "combined feed"});
            return parts;
        }

        if (terms.length >= 2) {
            const is = (term: NarrowTerm, expected: string): boolean =>
                Filter.canonicalize_operator(term.operator) === expected && !term.negated;

            if (is(terms[0], "channel") && is(terms[1], "topic")) {
                const channel = terms[0].operand;
                const topic = terms[1].operand;
                parts.push({
                    type: "channel_topic",
                    channel,
                    topic,
                });
                terms = terms.slice(2);
            }
        }

        const more_parts = terms.map((term): Part => {
            const operand = term.operand;
            const canonicalized_operator = Filter.canonicalize_operator(term.operator);
            if (canonicalized_operator === "is") {
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
                ];
                if (!valid_has_operands.includes(operand)) {
                    return {
                        type: "invalid_has",
                        operand,
                    };
                }
            }
            const prefix_for_operator = Filter.operator_to_prefix(
                canonicalized_operator,
                term.negated,
            );
            if (prefix_for_operator !== "") {
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

    static search_description_as_html(terms: NarrowTerm[]): string {
        return render_search_description({
            parts: Filter.parts_for_describe(terms),
        });
    }

    static is_spectator_compatible(terms: NarrowTerm[]): boolean {
        for (const term of terms) {
            if (term.operand === undefined) {
                return false;
            }
            if (!hash_parser.allowed_web_public_narrows.includes(term.operator)) {
                return false;
            }
        }
        return true;
    }

    predicate(): (message: Message) => boolean {
        if (this._predicate === undefined) {
            this._predicate = this._build_predicate();
        }
        return this._predicate;
    }

    terms(): NarrowTerm[] {
        return this._terms;
    }

    public_terms(): NarrowTerm[] {
        const safe_to_return = this._terms.filter(
            // Filter out the embedded narrow (if any).
            (term) =>
                !(
                    page_params.narrow_stream !== undefined &&
                    term.operator === "channel" &&
                    term.operand.toLowerCase() === page_params.narrow_stream.toLowerCase()
                ),
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
        return this._terms.length === 1 && this.has_operand("in", "home");
    }

    is_keyword_search(): boolean {
        return this.has_operator("search");
    }

    is_non_huddle_pm(): boolean {
        return this.has_operator("dm") && this.operands("dm")[0].split(",").length === 1;
    }

    supports_collapsing_recipients(): boolean {
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
            "in-home",
            "in-all",
            "channels-public",
            "not-channels-public",
            "channels-web-public",
            "not-channels-web-public",
            "near",
        ]);

        for (const term of term_types) {
            if (!valid_term_types.has(term)) {
                return false;
            }
        }
        return true;
    }

    calc_can_mark_messages_read(): boolean {
        // Arguably this should match supports_collapsing_recipients.
        // We may want to standardize on that in the future.  (At
        // present, this function does not allow combining valid filters).
        if (this.single_term_type_returns_all_messages_of_conversation()) {
            return true;
        }
        return false;
    }

    can_mark_messages_read(): boolean {
        if (this._can_mark_messages_read === undefined) {
            this._can_mark_messages_read = this.calc_can_mark_messages_read();
        }
        return this._can_mark_messages_read;
    }

    single_term_type_returns_all_messages_of_conversation(): boolean {
        const term_types = this.sorted_term_types();

        // "topic" alone cannot guarantee all messages of a conversation because
        // it is limited by the user's message history. Therefore, we check "channel"
        // and "topic" together to ensure that the current filter will return all the
        // messages of a conversation.
        if (_.isEqual(term_types, ["channel", "topic"])) {
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

        if (_.isEqual(term_types, ["is-resolved"])) {
            return true;
        }

        if (_.isEqual(term_types, ["in-home"])) {
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
        if (_.isEqual(term_types, ["channel", "topic", "search"])) {
            // if channel does not exist, redirect to home view
            if (!this._sub) {
                return "#";
            }
            return (
                "/#narrow/" +
                CHANNEL_SYNONYM +
                "/" +
                stream_data.name_to_slug(this.operands("channel")[0]) +
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
                case "channel":
                    // if channel does not exist, redirect to home view
                    if (!this._sub) {
                        return "#";
                    }
                    return (
                        "/#narrow/" +
                        CHANNEL_SYNONYM +
                        "/" +
                        stream_data.name_to_slug(this.operands("channel")[0])
                    );
                case "is-dm":
                    return "/#narrow/is/dm";
                case "is-starred":
                    return "/#narrow/is/starred";
                case "is-mentioned":
                    return "/#narrow/is/mentioned";
                case "channels-public":
                    return "/#narrow/" + CHANNELS_SYNONYM + "/public";
                case "dm":
                    return "/#narrow/dm/" + people.emails_to_slug(this.operands("dm").join(","));
                case "is-resolved":
                    return "/#narrow/topics/is/resolved";
                // TODO: It is ambiguous how we want to handle the 'sender' case,
                // we may remove it in the future based on design decisions
                case "sender":
                    return "/#narrow/sender/" + people.emails_to_slug(this.operands("sender")[0]);
            }
        }

        return "#"; // redirect to All
    }

    add_icon_data(context: {title: string; is_spectator: boolean}): IconData {
        // We have special icons for the simple narrows available for the via sidebars.
        const term_types = this.sorted_term_types();
        let icon;
        let zulip_icon;
        switch (term_types[0]) {
            case "in-home":
            case "in-all":
                icon = "home";
                break;
            case "channel":
                if (!this._sub) {
                    icon = "question-circle-o";
                    break;
                }
                if (this._sub.invite_only) {
                    zulip_icon = "lock";
                    break;
                }
                if (this._sub.is_web_public) {
                    zulip_icon = "globe";
                    break;
                }
                zulip_icon = "hashtag";
                break;
            case "is-dm":
                icon = "envelope";
                break;
            case "is-starred":
                zulip_icon = "star-filled";
                break;
            case "is-mentioned":
                zulip_icon = "at-sign";
                break;
            case "dm":
                icon = "envelope";
                break;
            case "is-resolved":
                icon = "check";
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
            (term_types.length === 2 && _.isEqual(term_types, ["channel", "topic"])) ||
            (term_types.length === 1 && _.isEqual(term_types, ["channel"]))
        ) {
            if (!this._sub) {
                const search_text = this.operands("channel")[0];
                return $t({defaultMessage: "Unknown channel #{search_text}"}, {search_text});
            }
            return this._sub.name;
        }
        if (
            (term_types.length === 2 && _.isEqual(term_types, ["dm", "near"])) ||
            (term_types.length === 1 && _.isEqual(term_types, ["dm"]))
        ) {
            const emails = this.operands("dm")[0].split(",");
            const names = emails.map((email) => {
                const person = people.get_by_email(email);
                if (!person) {
                    return email;
                }

                if (people.should_add_guest_user_indicator(person.user_id)) {
                    return $t({defaultMessage: "{name} (guest)"}, {name: person.full_name});
                }
                return person.full_name;
            });
            return util.format_array_as_list(names, "long", "conjunction");
        }
        if (term_types.length === 1 && _.isEqual(term_types, ["sender"])) {
            const email = this.operands("sender")[0];
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
                    return $t({defaultMessage: "Messages in all public channels"});
                case "is-starred":
                    return $t({defaultMessage: "Starred messages"});
                case "is-mentioned":
                    return $t({defaultMessage: "Mentions"});
                case "is-dm":
                    return $t({defaultMessage: "Direct message feed"});
                case "is-resolved":
                    return $t({defaultMessage: "Topics marked as resolved"});
                // These cases return false for is_common_narrow, and therefore are not
                // formatted in the message view header. They are used in narrow.js to
                // update the browser title.
                case "is-alerted":
                    return $t({defaultMessage: "Alerted messages"});
                case "is-unread":
                    return $t({defaultMessage: "Unread messages"});
            }
        }
        /* istanbul ignore next */
        return undefined;
    }

    allow_use_first_unread_when_narrowing(): boolean {
        return this.can_mark_messages_read() || this.has_operator("is");
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
        return this.has_operand("is", "mentioned") || this.has_operand("is", "starred");
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
        if (!terms.some((term) => Filter.term_type(term) === "dm")) {
            return terms;
        }

        return terms.filter((term) => Filter.term_type(term) !== "is-dm");
    }

    _canonicalize_terms(terms_mixed_case: NarrowTerm[]): NarrowTerm[] {
        return terms_mixed_case.map((term: NarrowTerm) => Filter.canonicalize_term(term));
    }

    filter_with_new_params(params: NarrowTerm): Filter {
        const new_params = this.fix_terms([params])[0];
        const terms = this._terms.map((term) => {
            const new_term = {...term};
            if (new_term.operator === new_params.operator && !new_term.negated) {
                new_term.operand = new_params.operand;
            }
            return new_term;
        });
        return new Filter(terms);
    }

    has_topic(stream_name: string, topic: string): boolean {
        return this.has_operand("channel", stream_name) && this.has_operand("topic", topic);
    }

    sorted_term_types(): string[] {
        if (this._sorted_term_types === undefined) {
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

    is_conversation_view(): boolean {
        const term_type = this.sorted_term_types();
        if (_.isEqual(term_type, ["channel", "topic"]) || _.isEqual(term_type, ["dm"])) {
            return true;
        }
        return false;
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
            !this.has_operand("is", "starred")
        );
    }
}
