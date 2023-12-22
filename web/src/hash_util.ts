import * as internal_url from "../shared/src/internal_url";

import type {Message} from "./message_store";
import * as people from "./people";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import type {StreamSubscription} from "./sub_store";
import type {UserGroup} from "./user_groups";

type Operator = {operator: string; operand: string; negated?: boolean};

export function build_reload_url(): string {
    let hash = window.location.hash;
    if (hash.length !== 0 && hash.startsWith("#")) {
        hash = hash.slice(1);
    }
    return "+oldhash=" + encodeURIComponent(hash);
}

export function encode_operand(operator: string, operand: string): string {
    if (
        operator === "group-pm-with" ||
        operator === "dm-including" ||
        operator === "dm" ||
        operator === "sender" ||
        operator === "pm-with"
    ) {
        const slug = people.emails_to_slug(operand);
        if (slug) {
            return slug;
        }
    }

    if (operator === "stream") {
        return encode_stream_name(operand);
    }

    return internal_url.encodeHashComponent(operand);
}

export function encode_stream_name(operand: string): string {
    // stream_data prefixes the stream id, but it does not do the
    // URI encoding piece
    operand = stream_data.name_to_slug(operand);

    return internal_url.encodeHashComponent(operand);
}

export function decode_operand(operator: string, operand: string): string {
    if (
        operator === "group-pm-with" ||
        operator === "dm-including" ||
        operator === "dm" ||
        operator === "sender" ||
        operator === "pm-with"
    ) {
        const emails = people.slug_to_emails(operand);
        if (emails) {
            return emails;
        }
    }

    operand = internal_url.decodeHashComponent(operand);

    if (operator === "stream") {
        return stream_data.slug_to_name(operand);
    }

    return operand;
}

export function by_stream_url(stream_id: number): string {
    // Wrapper for web use of internal_url.by_stream_url
    return internal_url.by_stream_url(stream_id, sub_store.maybe_get_stream_name);
}

export function by_stream_topic_url(stream_id: number, topic: string): string {
    // Wrapper for web use of internal_url.by_stream_topic_url
    return internal_url.by_stream_topic_url(stream_id, topic, sub_store.maybe_get_stream_name);
}

// Encodes an operator list into the
// corresponding hash: the # component
// of the narrow URL
export function operators_to_hash(operators?: Operator[]): string {
    let hash = "#";

    if (operators !== undefined) {
        hash = "#narrow";

        for (const elem of operators) {
            // Support legacy tuples.
            const operator = elem.operator;
            const operand = elem.operand;

            const sign = elem.negated ? "-" : "";
            hash +=
                "/" +
                sign +
                internal_url.encodeHashComponent(operator) +
                "/" +
                encode_operand(operator, operand);
        }
    }

    return hash;
}

export function by_sender_url(reply_to: string): string {
    return operators_to_hash([{operator: "sender", operand: reply_to}]);
}

export function pm_with_url(reply_to: string): string {
    const slug = people.emails_to_slug(reply_to);
    return "#narrow/dm/" + slug;
}

export function huddle_with_url(user_ids_string: string): string {
    // This method is convenient for callers
    // that have already converted emails to a comma-delimited
    // list of user_ids.  We should be careful to keep this
    // consistent with hash_util.decode_operand.
    return "#narrow/dm/" + user_ids_string + "-group";
}

export function by_conversation_and_time_url(message: Message): string {
    const absolute_url =
        window.location.protocol +
        "//" +
        window.location.host +
        "/" +
        window.location.pathname.split("/")[1];

    const suffix = "/near/" + internal_url.encodeHashComponent(message.id.toString());

    if (message.type === "stream") {
        return absolute_url + by_stream_topic_url(message.stream_id, message.topic) + suffix;
    }

    return absolute_url + people.pm_perma_link(message) + suffix;
}

export function stream_edit_url(sub: StreamSubscription, right_side_tab: string): string {
    return `#streams/${sub.stream_id}/${internal_url.encodeHashComponent(
        sub.name,
    )}/${right_side_tab}`;
}

export function group_edit_url(group: UserGroup): string {
    const hash = `#groups/${group.id}/${internal_url.encodeHashComponent(group.name)}`;
    return hash;
}

export function search_public_streams_notice_url(operators: Operator[]): string {
    const public_operator = {operator: "streams", operand: "public"};
    return operators_to_hash([public_operator, ...operators]);
}

export function parse_narrow(hash: string): Operator[] | undefined {
    // This will throw an exception when passed an invalid hash
    // at the decodeHashComponent call, handle appropriately.
    let i;
    const operators = [];
    for (i = 1; i < hash.length; i += 2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        let operator = internal_url.decodeHashComponent(hash[i]);
        // Do not parse further if empty operator encountered.
        if (operator === "") {
            break;
        }

        const raw_operand = hash[i + 1];

        if (!raw_operand) {
            return undefined;
        }

        let negated = false;
        if (operator.startsWith("-")) {
            negated = true;
            operator = operator.slice(1);
        }

        const operand = decode_operand(operator, raw_operand);
        operators.push({negated, operator, operand});
    }
    return operators;
}
