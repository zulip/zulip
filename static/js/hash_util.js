import * as internal_url from "../shared/js/internal_url";

import * as people from "./people";
import * as stream_data from "./stream_data";

export function get_hash_category(hash) {
    // given "#streams/subscribed", returns "streams"
    return hash ? hash.replace(/^#/, "").split(/\//)[0] : "";
}

export function get_hash_section(hash) {
    // given "#settings/profile", returns "profile"
    // given '#streams/5/social", returns "5"
    if (!hash) {
        return "";
    }

    const parts = hash.replace(/\/$/, "").split(/\//);

    return parts[1] || "";
}

export function get_current_hash_category() {
    return get_hash_category(window.location.hash);
}

export function get_current_hash_section() {
    return get_hash_section(window.location.hash);
}

export function build_reload_url() {
    let hash = window.location.hash;
    if (hash.length !== 0 && hash[0] === "#") {
        hash = hash.slice(1);
    }
    return "+oldhash=" + encodeURIComponent(hash);
}

export function encode_operand(operator, operand) {
    if (operator === "group-pm-with" || operator === "pm-with" || operator === "sender") {
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

export function encode_stream_name(operand) {
    // stream_data prefixes the stream id, but it does not do the
    // URI encoding piece
    operand = stream_data.name_to_slug(operand);

    return internal_url.encodeHashComponent(operand);
}

export function decode_operand(operator, operand) {
    if (operator === "group-pm-with" || operator === "pm-with" || operator === "sender") {
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

export function by_stream_url(stream_id) {
    // Wrapper for web use of internal_url.by_stream_url
    return internal_url.by_stream_url(stream_id, stream_data.maybe_get_stream_name);
}

export function by_stream_topic_url(stream_id, topic) {
    // Wrapper for web use of internal_url.by_stream_topic_url
    return internal_url.by_stream_topic_url(stream_id, topic, stream_data.maybe_get_stream_name);
}

// Encodes an operator list into the
// corresponding hash: the # component
// of the narrow URL
export function operators_to_hash(operators) {
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

export function by_sender_url(reply_to) {
    return operators_to_hash([{operator: "sender", operand: reply_to}]);
}

export function pm_with_url(reply_to) {
    const slug = people.emails_to_slug(reply_to);
    return "#narrow/pm-with/" + slug;
}

export function huddle_with_url(user_ids_string) {
    // This method is convenient for callers
    // that have already converted emails to a comma-delimited
    // list of user_ids.  We should be careful to keep this
    // consistent with hash_util.decode_operand.
    return "#narrow/pm-with/" + user_ids_string + "-group";
}

export function by_conversation_and_time_url(message) {
    const absolute_url =
        window.location.protocol +
        "//" +
        window.location.host +
        "/" +
        window.location.pathname.split("/")[1];

    const suffix = "/near/" + internal_url.encodeHashComponent(message.id);

    if (message.type === "stream") {
        return absolute_url + by_stream_topic_url(message.stream_id, message.topic) + suffix;
    }

    return absolute_url + people.pm_perma_link(message) + suffix;
}

export function stream_edit_url(sub) {
    const hash = `#streams/${sub.stream_id}/${internal_url.encodeHashComponent(sub.name)}`;
    return hash;
}

export function search_public_streams_notice_url(operators) {
    const public_operator = {operator: "streams", operand: "public"};
    return operators_to_hash([public_operator].concat(operators));
}

export function parse_narrow(hash) {
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
        if (operator[0] === "-") {
            negated = true;
            operator = operator.slice(1);
        }

        const operand = decode_operand(operator, raw_operand);
        operators.push({negated, operator, operand});
    }
    return operators;
}

export function is_overlay_hash(hash) {
    // Hash changes within this list are overlays and should not unnarrow (etc.)
    const overlay_list = [
        "streams",
        "drafts",
        "settings",
        "organization",
        "invite",
        "keyboard-shortcuts",
        "message-formatting",
        "search-operators",
        "about-zulip",
    ];
    const main_hash = get_hash_category(hash);

    return overlay_list.includes(main_hash);
}

// this finds the stream that is actively open in the settings and focused in
// the left side.
export function is_editing_stream(desired_stream_id) {
    const hash_components = window.location.hash.slice(1).split(/\//);

    if (hash_components[0] !== "streams") {
        return false;
    }

    if (!hash_components[2]) {
        return false;
    }

    // if the string casted to a number is valid, and another component
    // after exists then it's a stream name/id pair.
    const stream_id = Number.parseFloat(hash_components[1]);

    return stream_id === desired_stream_id;
}

export function is_create_new_stream_narrow() {
    return window.location.hash === "#streams/new";
}

export const allowed_web_public_narrows = [
    "streams",
    "stream",
    "topic",
    "sender",
    "has",
    "search",
    "near",
    "id",
];

export function is_spectator_compatible(hash) {
    // Defines which views are supported for spectators.
    // This implementation should agree with the similar function in zerver/lib/narrow.py.
    const web_public_allowed_hashes = [
        "",
        "narrow", // full #narrow hash handled in narrow.is_spectator_compatible
        "recent_topics",
        "keyboard-shortcuts",
        "message-formatting",
        "search-operators",
        "all_messages",
        "about-zulip",
    ];

    const main_hash = get_hash_category(hash);

    if (main_hash === "narrow") {
        const hash_section = get_hash_section(hash);
        if (!allowed_web_public_narrows.includes(hash_section)) {
            return false;
        }
        return true;
    }

    return web_public_allowed_hashes.includes(main_hash);
}

export function current_hash_as_next() {
    return `next=/${encodeURIComponent(window.location.hash)}`;
}
