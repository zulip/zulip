import _ from "lodash";

import * as resolved_topic from "../shared/src/resolved_topic";
import render_search_description from "../templates/search_description.hbs";

import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_parser from "./message_parser";
import * as message_store from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import * as stream_data from "./stream_data";
import * as unread from "./unread";
import * as user_topics from "./user_topics";
import * as util from "./util";

function zephyr_stream_name_match(message, operand) {
    // Zephyr users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
    // (unsocial, ununsocial, social.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(?:un)*(.+?)(?:\.d)*$/i.exec(operand);
    let base_stream_name = operand;
    if (m !== null && m[1] !== undefined) {
        base_stream_name = m[1];
    }
    const related_regexp = new RegExp(
        /^(un)*/.source + _.escapeRegExp(base_stream_name) + /(\.d)*$/.source,
        "i",
    );
    const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    return related_regexp.test(stream_name);
}

function zephyr_topic_name_match(message, operand) {
    // Zephyr users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
    // (foo, foo.d, foo.d.d, etc)
    // TODO: hoist the regex compiling out of the closure
    const m = /^(.*?)(?:\.d)*$/i.exec(operand);
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

function message_in_home(message) {
    // The home view contains messages not sent to muted streams, with
    // additional logic for unmuted topics, mentions, and
    // single-stream windows.
    const stream_name = stream_data.get_stream_name_from_id(message.stream_id);
    if (
        message.type === "private" ||
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

function message_matches_search_term(message, operator, operand) {
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

        case "stream": {
            if (message.type !== "stream") {
                return false;
            }

            operand = operand.toLowerCase();
            if (page_params.realm_is_zephyr_mirror_realm) {
                return zephyr_stream_name_match(message, operand);
            }

            // Try to match by stream_id if have a valid sub for
            // the operand. If we can't find the id, we return false.
            const stream_id = stream_data.get_stream_id(operand);
            return stream_id && message.stream_id === stream_id;
        }

        case "topic":
            if (message.type !== "stream") {
                return false;
            }

            operand = operand.toLowerCase();
            if (page_params.realm_is_zephyr_mirror_realm) {
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
    constructor(operators) {
        if (operators === undefined) {
            this._operators = [];
            this._sub = undefined;
        } else {
            this._operators = this.fix_operators(operators);
            if (this.has_operator("stream")) {
                this._sub = stream_data.get_sub_by_name(this.operands("stream")[0]);
            }
        }
    }

    static canonicalize_operator(operator) {
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
        return operator;
    }

    static canonicalize_term({negated = false, operator, operand}) {
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

            case "stream":
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
    static encodeOperand(operand) {
        return operand
            .replaceAll("%", "%25")
            .replaceAll("+", "%2B")
            .replaceAll(" ", "+")
            .replaceAll('"', "%22");
    }

    static decodeOperand(encoded, operator) {
        encoded = encoded.replaceAll('"', "");
        if (
            ["dm-including", "dm", "sender", "from", "pm-with", "group-pm-with"].includes(
                operator,
            ) === false
        ) {
            encoded = encoded.replaceAll("+", " ");
        }
        return util.robust_url_decode(encoded).trim();
    }

    // Parse a string into a list of operators (see below).
    static parse(str) {
        const operators = [];
        let search_term = [];
        let negated;
        let operator;
        let operand;
        let term;

        function maybe_add_search_terms() {
            if (search_term.length > 0) {
                operator = "search";
                const _operand = search_term.join(" ");
                term = {operator, operand: _operand, negated: false};
                operators.push(term);
                search_term = [];
            }
        }

        // Match all operands that either have no spaces, or are surrounded by
        // quotes, preceded by an optional operator that may have a space after it.
        const matches = str.match(/([^\s:]+: ?)?("[^"]+"?|\S+)/g);
        if (matches === null) {
            return operators;
        }

        for (const token of matches) {
            let operator;
            const parts = token.split(":");
            if (token[0] === '"' || parts.length === 1) {
                // Looks like a normal search term.
                search_term.push(token);
            } else {
                // Looks like an operator.
                negated = false;
                operator = parts.shift();
                if (operator[0] === "-") {
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
                // operators list. This is done so that the last active filter is correctly
                // detected by the `get_search_result` function (in search_suggestions.js).
                maybe_add_search_terms();
                term = {negated, operator, operand};
                operators.push(term);
            }
        }

        maybe_add_search_terms();
        return operators;
    }

    /* Convert a list of operators to a string.
   Each operator is a key-value pair like

       ['topic', 'my amazing topic']

   These are not keys in a JavaScript object, because we
   might need to support multiple operators of the same type.
*/
    static unparse(operators) {
        const parts = operators.map((elem) => {
            if (elem.operator === "search") {
                // Search terms are the catch-all case.
                // All tokens that don't start with a known operator and
                // a colon are glued together to form a search term.
                return elem.operand;
            }
            const sign = elem.negated ? "-" : "";
            if (elem.operator === "") {
                return elem.operand;
            }
            return sign + elem.operator + ":" + Filter.encodeOperand(elem.operand.toString());
        });
        return parts.join(" ");
    }

    predicate() {
        if (this._predicate === undefined) {
            this._predicate = this._build_predicate();
        }
        return this._predicate;
    }

    operators() {
        return this._operators;
    }

    public_operators() {
        const safe_to_return = this._operators.filter(
            // Filter out the embedded narrow (if any).
            (value) =>
                !(
                    page_params.narrow_stream !== undefined &&
                    value.operator === "stream" &&
                    value.operand.toLowerCase() === page_params.narrow_stream.toLowerCase()
                ),
        );
        return safe_to_return;
    }

    operands(operator) {
        return this._operators
            .filter((elem) => !elem.negated && elem.operator === operator)
            .map((elem) => elem.operand);
    }

    has_negated_operand(operator, operand) {
        return this._operators.some(
            (elem) => elem.negated && elem.operator === operator && elem.operand === operand,
        );
    }

    has_operand(operator, operand) {
        return this._operators.some(
            (elem) => !elem.negated && elem.operator === operator && elem.operand === operand,
        );
    }

    has_operator(operator) {
        return this._operators.some((elem) => {
            if (elem.negated && !["search", "has"].includes(elem.operator)) {
                return false;
            }
            return elem.operator === operator;
        });
    }

    is_search() {
        return this.has_operator("search");
    }

    is_non_huddle_pm() {
        return this.has_operator("dm") && this.operands("dm")[0].split(",").length === 1;
    }

    supports_collapsing_recipients() {
        // Determines whether a view is guaranteed, by construction,
        // to contain consecutive messages in a given topic, and thus
        // it is appropriate to collapse recipient/sender headings.
        const term_types = this.sorted_term_types();

        // All search/narrow term types, including negations, with the
        // property that if a message is in the view, then any other
        // message sharing its recipient (stream/topic or direct
        // message recipient) must also be present in the view.
        const valid_term_types = new Set([
            "stream",
            "not-stream",
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
            "streams-public",
            "not-streams-public",
            "streams-web-public",
            "not-streams-web-public",
            "near",
        ]);

        for (const term of term_types) {
            if (!valid_term_types.has(term)) {
                return false;
            }
        }
        return true;
    }

    calc_can_mark_messages_read() {
        // Arguably this should match supports_collapsing_recipients.
        // We may want to standardize on that in the future.  (At
        // present, this function does not allow combining valid filters).
        if (this.single_term_type_returns_all_messages_of_conversation()) {
            return true;
        }
        const term_types = this.sorted_term_types();
        if (_.isEqual(term_types, [])) {
            // "All messages" view
            return true;
        }
        return false;
    }

    can_mark_messages_read() {
        if (this._can_mark_messages_read === undefined) {
            this._can_mark_messages_read = this.calc_can_mark_messages_read();
        }
        return this._can_mark_messages_read;
    }

    single_term_type_returns_all_messages_of_conversation() {
        const term_types = this.sorted_term_types();

        // "topic" alone cannot guarantee all messages of a conversation because
        // it is limited by the user's message history. Therefore, we check "stream"
        // and "topic" together to ensure that the current filter will return all the
        // messages of a conversation.
        if (_.isEqual(term_types, ["stream", "topic"])) {
            return true;
        }

        if (_.isEqual(term_types, ["dm"])) {
            return true;
        }

        if (_.isEqual(term_types, ["stream"])) {
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

        return false;
    }

    // This is used to control the behaviour for "exiting search",
    // given the ability to flip between displaying the search bar and the narrow description in UI
    // here we define a narrow as a "common narrow" on the basis of
    // https://paper.dropbox.com/doc/Navbar-behavior-table--AvnMKN4ogj3k2YF5jTbOiVv_AQ-cNOGtu7kSdtnKBizKXJge
    // common narrows show a narrow description and allow the user to
    // close search bar UI and show the narrow description UI.
    is_common_narrow() {
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
        if (_.isEqual(term_types, ["streams-public"])) {
            return true;
        }
        if (_.isEqual(term_types, ["sender"])) {
            return true;
        }
        return false;
    }

    // This is used to control the behaviour for "exiting search"
    // within a narrow (E.g. a stream/topic + search) to bring you to
    // the containing common narrow (stream/topic, in the example)
    // rather than "All messages".
    //
    // Note from tabbott: The slug-based approach may not be ideal; we
    // may be able to do better another way.
    generate_redirect_url() {
        const term_types = this.sorted_term_types();

        // this comes first because it has 3 term_types but is not a "complex filter"
        if (_.isEqual(term_types, ["stream", "topic", "search"])) {
            // if stream does not exist, redirect to All
            if (!this._sub) {
                return "#";
            }
            return (
                "/#narrow/stream/" +
                stream_data.name_to_slug(this.operands("stream")[0]) +
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
                case "stream":
                    // if stream does not exist, redirect to All
                    if (!this._sub) {
                        return "#";
                    }
                    return (
                        "/#narrow/stream/" + stream_data.name_to_slug(this.operands("stream")[0])
                    );
                case "is-dm":
                    return "/#narrow/is/dm";
                case "is-starred":
                    return "/#narrow/is/starred";
                case "is-mentioned":
                    return "/#narrow/is/mentioned";
                case "streams-public":
                    return "/#narrow/streams/public";
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

    add_icon_data(context) {
        // We have special icons for the simple narrows available for the via sidebars.
        const term_types = this.sorted_term_types();
        switch (term_types[0]) {
            case "in-home":
            case "in-all":
                context.icon = "home";
                break;
            case "stream":
                if (!this._sub) {
                    context.icon = "question-circle-o";
                    break;
                }
                if (this._sub.invite_only) {
                    context.zulip_icon = "lock";
                    break;
                }
                if (this._sub.is_web_public) {
                    context.zulip_icon = "globe";
                    break;
                }
                context.zulip_icon = "hashtag";
                break;
            case "is-dm":
                context.icon = "envelope";
                break;
            case "is-starred":
                context.icon = "star";
                break;
            case "is-mentioned":
                context.icon = "at";
                break;
            case "dm":
                context.icon = "envelope";
                break;
            case "is-resolved":
                context.icon = "check";
                break;
            default:
                context.icon = undefined;
                break;
        }
    }

    get_title() {
        // Nice explanatory titles for common views.
        const term_types = this.sorted_term_types();
        if (
            (term_types.length === 3 && _.isEqual(term_types, ["stream", "topic", "near"])) ||
            (term_types.length === 2 && _.isEqual(term_types, ["stream", "topic"])) ||
            (term_types.length === 1 && _.isEqual(term_types, ["stream"]))
        ) {
            if (!this._sub) {
                const search_text = this.operands("stream")[0];
                return $t({defaultMessage: "Unknown stream #{search_text}"}, {search_text});
            }
            return this._sub.name;
        }
        if (
            (term_types.length === 2 && _.isEqual(term_types, ["dm", "near"])) ||
            (term_types.length === 1 && _.isEqual(term_types, ["dm"]))
        ) {
            const emails = this.operands("dm")[0].split(",");
            const names = emails.map((email) => {
                if (!people.get_by_email(email)) {
                    return email;
                }
                return people.get_by_email(email).full_name;
            });

            // We use join to handle the addition of a comma and space after every name
            // and also to ensure that we return a string and not an array so that we
            // can have the same return type as other cases.
            return names.join(", ");
        }
        if (term_types.length === 1 && _.isEqual(term_types, ["sender"])) {
            const email = this.operands("sender")[0];
            const user = people.get_by_email(email);
            let sender = email;
            if (user) {
                if (people.is_my_user_id(user.user_id)) {
                    return $t({defaultMessage: "Messages sent by you"});
                }
                sender = user.full_name;
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
                    return $t({defaultMessage: "All messages"});
                case "in-all":
                    return $t({defaultMessage: "All messages including muted streams"});
                case "streams-public":
                    return $t({defaultMessage: "Messages in all public streams"});
                case "is-starred":
                    return $t({defaultMessage: "Starred messages"});
                case "is-mentioned":
                    return $t({defaultMessage: "Mentions"});
                case "is-dm":
                    return $t({defaultMessage: "Direct messages"});
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

    allow_use_first_unread_when_narrowing() {
        return this.can_mark_messages_read() || this.has_operator("is");
    }

    contains_only_private_messages() {
        return (
            (this.has_operator("is") && this.operands("is")[0] === "dm") ||
            this.has_operator("dm") ||
            this.has_operator("dm-including")
        );
    }

    includes_full_stream_history() {
        return this.has_operator("stream") || this.has_operator("streams");
    }

    is_personal_filter() {
        // Whether the filter filters for user-specific data in the
        // UserMessage table, such as stars or mentions.
        //
        // Such filters should not advertise "streams:public" as it
        // will never add additional results.
        return this.has_operand("is", "mentioned") || this.has_operand("is", "starred");
    }

    can_apply_locally(is_local_echo) {
        // Since there can be multiple operators, each block should
        // just return false here.

        if (this.is_search()) {
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

        // TODO: It's not clear why `streams:` filters would not be
        // applicable locally.
        if (this.has_operator("streams") || this.has_negated_operand("streams", "public")) {
            return false;
        }

        // If we get this far, we're good!
        return true;
    }

    fix_operators(operators) {
        operators = this._canonicalize_operators(operators);
        operators = this._fix_redundant_is_private(operators);
        return operators;
    }

    _fix_redundant_is_private(terms) {
        if (!terms.some((term) => Filter.term_type(term) === "dm")) {
            return terms;
        }

        return terms.filter((term) => Filter.term_type(term) !== "is-dm");
    }

    _canonicalize_operators(operators_mixed_case) {
        return operators_mixed_case.map((tuple) => Filter.canonicalize_term(tuple));
    }

    filter_with_new_params(params) {
        const terms = this._operators.map((term) => {
            const new_term = {...term};
            if (new_term.operator === params.operator && !new_term.negated) {
                new_term.operand = params.operand;
            }
            return new_term;
        });
        return new Filter(terms);
    }

    has_topic(stream_name, topic) {
        return this.has_operand("stream", stream_name) && this.has_operand("topic", topic);
    }

    sorted_term_types() {
        if (this._sorted_term_types === undefined) {
            this._sorted_term_types = this._build_sorted_term_types();
        }
        return this._sorted_term_types;
    }

    _build_sorted_term_types() {
        const terms = this._operators;
        const term_types = terms.map((term) => Filter.term_type(term));
        const sorted_terms = Filter.sorted_term_types(term_types);
        return sorted_terms;
    }

    can_bucket_by(...wanted_term_types) {
        // Examples call:
        //     filter.can_bucket_by('stream', 'topic')
        //
        // The use case of this function is that we want
        // to know if a filter can start with a bucketing
        // data structure similar to the ones we have in
        // unread.js to pre-filter ids, rather than apply
        // a predicate to a larger list of candidate ids.
        //
        // (It's for optimization, basically.)
        const all_term_types = this.sorted_term_types();
        const term_types = all_term_types.slice(0, wanted_term_types.length);

        return _.isEqual(term_types, wanted_term_types);
    }

    first_valid_id_from(msg_ids) {
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

    update_email(user_id, new_email) {
        for (const term of this._operators) {
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
    _build_predicate() {
        const operators = this._operators;

        if (!this.can_apply_locally()) {
            return () => true;
        }

        // FIXME: This is probably pretty slow.
        // We could turn it into something more like a compiler:
        // build JavaScript code in a string and then eval() it.

        return (message) =>
            operators.every((term) => {
                let ok = message_matches_search_term(message, term.operator, term.operand);
                if (term.negated) {
                    ok = !ok;
                }
                return ok;
            });
    }

    static term_type(term) {
        const operator = term.operator;
        const operand = term.operand;
        const negated = term.negated;

        let result = negated ? "not-" : "";

        result += operator;

        if (["is", "has", "in", "streams"].includes(operator)) {
            result += "-" + operand;
        }

        return result;
    }

    static sorted_term_types(term_types) {
        const levels = [
            "in",
            "streams-public",
            "stream",
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

        const level = (term_type) => {
            let i = levels.indexOf(term_type);
            if (i === -1) {
                i = 999;
            }
            return i;
        };

        const compare = (a, b) => {
            const diff = level(a) - level(b);
            if (diff !== 0) {
                return diff;
            }
            return util.strcmp(a, b);
        };

        return [...term_types].sort(compare);
    }

    static operator_to_prefix(operator, negated) {
        operator = Filter.canonicalize_operator(operator);

        if (operator === "search") {
            return negated ? "exclude" : "search for";
        }

        const verb = negated ? "exclude " : "";

        switch (operator) {
            case "stream":
                return verb + "stream";
            case "streams":
                return verb + "streams";
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

    // Convert a list of operators to a human-readable description.
    static parts_for_describe(operators) {
        const parts = [];

        if (operators.length === 0) {
            parts.push({type: "plain_text", content: "all messages"});
            return parts;
        }

        if (operators.length >= 2) {
            const is = (term, expected) => term.operator === expected && !term.negated;

            if (is(operators[0], "stream") && is(operators[1], "topic")) {
                const stream = operators[0].operand;
                const topic = operators[1].operand;
                parts.push({
                    type: "stream_topic",
                    stream,
                    topic,
                });
                operators = operators.slice(2);
            }
        }

        const more_parts = operators.map((elem) => {
            const operand = elem.operand;
            const canonicalized_operator = Filter.canonicalize_operator(elem.operator);
            if (canonicalized_operator === "is") {
                const verb = elem.negated ? "exclude " : "";
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
                elem.negated,
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

    static search_description_as_html(operators) {
        return render_search_description({
            parts: Filter.parts_for_describe(operators),
        });
    }

    static is_spectator_compatible(ops) {
        for (const op of ops) {
            if (op.operand === undefined) {
                return false;
            }
            if (!hash_util.allowed_web_public_narrows.includes(op.operator)) {
                return false;
            }
        }
        return true;
    }

    is_conversation_view() {
        const term_type = this.sorted_term_types();
        if (_.isEqual(term_type, ["stream", "topic"]) || _.isEqual(term_type, ["dm"])) {
            return true;
        }
        return false;
    }
}
