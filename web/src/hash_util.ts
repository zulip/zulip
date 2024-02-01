import * as internal_url from "../shared/src/internal_url";

import * as blueslip from "./blueslip";
import type {Message} from "./message_store";
import {page_params} from "./page_params";
import * as people from "./people";
import * as settings_data from "./settings_data";
import * as stream_data from "./stream_data";
import * as sub_store from "./sub_store";
import type {StreamSubscription} from "./sub_store";
import type {UserGroup} from "./user_groups";

// TODO(typescript): Move to filter.js when it's converted to typescript.
type Term = {operator: string; operand: string; negated?: boolean};

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

// Encodes a term list into the
// corresponding hash: the # component
// of the narrow URL
export function search_terms_to_hash(terms?: Term[]): string {
    let hash = "#";

    if (terms !== undefined) {
        hash = "#narrow";

        for (const term of terms) {
            // Support legacy tuples.
            const operator = term.operator;
            const operand = term.operand;

            const sign = term.negated ? "-" : "";
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
    return search_terms_to_hash([{operator: "sender", operand: reply_to}]);
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

export function group_edit_url(group: UserGroup, right_side_tab: string): string {
    const hash = `#groups/${group.id}/${internal_url.encodeHashComponent(group.name)}/${right_side_tab}`;
    return hash;
}

export function search_public_streams_notice_url(terms: Term[]): string {
    const public_operator = {operator: "streams", operand: "public"};
    return search_terms_to_hash([public_operator, ...terms]);
}

export function parse_narrow(hash: string): Term[] | undefined {
    // This will throw an exception when passed an invalid hash
    // at the decodeHashComponent call, handle appropriately.
    let i;
    const terms = [];
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
        terms.push({negated, operator, operand});
    }
    return terms;
}

export function validate_stream_settings_hash(hash: string): string {
    const hash_components = hash.slice(1).split(/\//);
    const section = hash_components[1];

    const can_create_streams =
        settings_data.user_can_create_public_streams() ||
        settings_data.user_can_create_web_public_streams() ||
        settings_data.user_can_create_private_streams();
    if (section === "new" && !can_create_streams) {
        return "#streams/subscribed";
    }

    if (/\d+/.test(section)) {
        const stream_id = Number.parseInt(section, 10);
        const sub = sub_store.get(stream_id);
        // There are a few situations where we can't display stream settings:
        // 1. This is a stream that's been archived. (sub=undefined)
        // 2. The stream ID is invalid. (sub=undefined)
        // 3. The current user is a guest, and was unsubscribed from the stream
        //    stream in the current session. (In future sessions, the stream will
        //    not be in sub_store).
        //
        // In all these cases we redirect the user to 'subscribed' tab.
        if (sub === undefined || (page_params.is_guest && !stream_data.is_subscribed(stream_id))) {
            return "#streams/subscribed";
        }

        const stream_name = hash_components[2];
        let right_side_tab = hash_components[3];
        const valid_right_side_tab_values = new Set(["general", "personal", "subscribers"]);
        if (sub.name === stream_name && valid_right_side_tab_values.has(right_side_tab)) {
            return hash;
        }
        if (!valid_right_side_tab_values.has(right_side_tab)) {
            right_side_tab = "general";
        }
        return stream_edit_url(sub, right_side_tab);
    }

    const valid_section_values = ["new", "subscribed", "all"];
    if (!valid_section_values.includes(section)) {
        blueslip.warn("invalid section for streams: " + section);
        return "#streams/subscribed";
    }
    return hash;
}
