"use strict";

const people = require("./people");

exports.get_hash_category = function (hash) {
    // given "#streams/subscribed", returns "streams"
    return hash ? hash.replace(/^#/, "").split(/\//)[0] : "";
};

exports.get_hash_section = function (hash) {
    // given "#settings/your-account", returns "your-account"
    // given '#streams/5/social", returns "5"
    if (!hash) {
        return "";
    }

    const parts = hash.replace(/\/$/, "").split(/\//);

    return parts[1] || "";
};

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).
exports.encodeHashComponent = function (str) {
    return encodeURIComponent(str).replace(/\./g, "%2E").replace(/%/g, ".");
};

exports.encode_operand = function (operator, operand) {
    if (operator === "group-pm-with" || operator === "pm-with" || operator === "sender") {
        const slug = people.emails_to_slug(operand);
        if (slug) {
            return slug;
        }
    }

    if (operator === "stream") {
        return exports.encode_stream_name(operand);
    }

    return exports.encodeHashComponent(operand);
};

exports.encode_stream_id = function (stream_id) {
    // stream_data appends the stream name, but it does not do the
    // URI encoding piece
    const slug = stream_data.id_to_slug(stream_id);

    return exports.encodeHashComponent(slug);
};

exports.encode_stream_name = function (operand) {
    // stream_data prefixes the stream id, but it does not do the
    // URI encoding piece
    operand = stream_data.name_to_slug(operand);

    return exports.encodeHashComponent(operand);
};

exports.decodeHashComponent = function (str) {
    try {
        // This fails for URLS containing
        // foo.foo or foo%foo due to our fault in special handling
        // of such characters when encoding. This can also,
        // fail independent of our fault, so just tell the user
        // that the url is invalid.
        // TODO: Show possible valid urls to the user.
        return decodeURIComponent(str.replace(/\./g, "%"));
    } catch (e) {
        ui_report.error(i18n.t("Invalid URL"), undefined, $("#home-error"), 2000);
        return "";
    }
};

exports.decode_operand = function (operator, operand) {
    if (operator === "group-pm-with" || operator === "pm-with" || operator === "sender") {
        const emails = people.slug_to_emails(operand);
        if (emails) {
            return emails;
        }
    }

    operand = exports.decodeHashComponent(operand);

    if (operator === "stream") {
        return stream_data.slug_to_name(operand);
    }

    return operand;
};

exports.by_stream_uri = function (stream_id) {
    return "#narrow/stream/" + exports.encode_stream_id(stream_id);
};

exports.by_stream_topic_uri = function (stream_id, topic) {
    return (
        "#narrow/stream/" +
        exports.encode_stream_id(stream_id) +
        "/topic/" +
        exports.encodeHashComponent(topic)
    );
};

// Encodes an operator list into the
// corresponding hash: the # component
// of the narrow URL
exports.operators_to_hash = function (operators) {
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
                exports.encodeHashComponent(operator) +
                "/" +
                exports.encode_operand(operator, operand);
        }
    }

    return hash;
};

exports.by_sender_uri = function (reply_to) {
    return exports.operators_to_hash([{operator: "sender", operand: reply_to}]);
};

exports.pm_with_uri = function (reply_to) {
    const slug = people.emails_to_slug(reply_to);
    return "#narrow/pm-with/" + slug;
};

exports.huddle_with_uri = function (user_ids_string) {
    // This method is convenient for callers
    // that have already converted emails to a comma-delimited
    // list of user_ids.  We should be careful to keep this
    // consistent with hash_util.decode_operand.
    return "#narrow/pm-with/" + user_ids_string + "-group";
};

exports.by_conversation_and_time_uri = function (message) {
    const absolute_url =
        window.location.protocol +
        "//" +
        window.location.host +
        "/" +
        window.location.pathname.split("/")[1];

    const suffix = "/near/" + exports.encodeHashComponent(message.id);

    if (message.type === "stream") {
        return (
            absolute_url + exports.by_stream_topic_uri(message.stream_id, message.topic) + suffix
        );
    }

    return absolute_url + people.pm_perma_link(message) + suffix;
};

exports.stream_edit_uri = function (sub) {
    const hash = "#streams" + "/" + sub.stream_id + "/" + exports.encodeHashComponent(sub.name);
    return hash;
};

exports.search_public_streams_notice_url = function () {
    // Computes the URL of the current narrow if streams:public were added.
    const operators = narrow_state.filter().operators();
    const public_operator = {operator: "streams", operand: "public"};
    return exports.operators_to_hash([public_operator].concat(operators));
};

exports.parse_narrow = function (hash) {
    let i;
    const operators = [];
    for (i = 1; i < hash.length; i += 2) {
        // We don't construct URLs with an odd number of components,
        // but the user might write one.
        let operator = exports.decodeHashComponent(hash[i]);
        // Do not parse further if empty operator encountered.
        if (operator === "") {
            break;
        }

        const raw_operand = hash[i + 1];

        if (!raw_operand) {
            return;
        }

        let negated = false;
        if (operator[0] === "-") {
            negated = true;
            operator = operator.slice(1);
        }

        const operand = exports.decode_operand(operator, raw_operand);
        operators.push({negated, operator, operand});
    }
    return operators;
};

window.hash_util = exports;
