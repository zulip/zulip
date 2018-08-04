var hash_util = (function () {

var exports = {};

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).
exports.encodeHashComponent = function (str) {
    return encodeURIComponent(str)
        .replace(/\./g, '%2E')
        .replace(/%/g, '.');
};

exports.encode_operand = function (operator, operand) {
    if (operator === 'group-pm-with' || operator === 'pm-with' || operator === 'sender') {
        var slug = people.emails_to_slug(operand);
        if (slug) {
            return slug;
        }
    }

    if (operator === 'stream') {
        return exports.encode_stream_name(operand);
    }

    return exports.encodeHashComponent(operand);
};

exports.encode_stream_name = function (operand) {
    // stream_data prefixes the stream id, but it does not do the
    // URI encoding piece
    operand = stream_data.name_to_slug(operand);

    return exports.encodeHashComponent(operand);
};

exports.decodeHashComponent = function (str) {
    return decodeURIComponent(str.replace(/\./g, '%'));
};

exports.decode_operand = function (operator, operand) {
    if (operator === 'group-pm-with' || operator === 'pm-with' || operator === 'sender') {
        var emails = people.slug_to_emails(operand);
        if (emails) {
            return emails;
        }
    }

    operand = exports.decodeHashComponent(operand);

    if (operator === 'stream') {
        return stream_data.slug_to_name(operand);
    }

    return operand;
};

exports.by_stream_uri = function (stream) {
    return "#narrow/stream/" + exports.encode_stream_name(stream);
};

exports.by_stream_subject_uri = function (stream, subject) {
    return "#narrow/stream/" + exports.encode_stream_name(stream) +
           "/subject/" + exports.encodeHashComponent(subject);
};

// Encodes an operator list into the
// corresponding hash: the # component
// of the narrow URL
exports.operators_to_hash = function (operators) {
    var hash = '#';

    if (operators !== undefined) {
        hash = '#narrow';
        _.each(operators, function (elem) {
            // Support legacy tuples.
            var operator = elem.operator;
            var operand = elem.operand;

            var sign = elem.negated ? '-' : '';
            hash += '/' + sign + exports.encodeHashComponent(operator)
                  + '/' + exports.encode_operand(operator, operand);
        });
    }

    return hash;
};

exports.by_sender_uri = function (reply_to) {
    return exports.operators_to_hash([
        {operator: 'sender', operand: reply_to},
    ]);
};

exports.pm_with_uri = function (reply_to) {
    return exports.operators_to_hash([
        {operator: 'pm-with', operand: reply_to},
    ]);
};

exports.huddle_with_uri = function (user_ids_string) {
    // This method is convenient for callers
    // that have already converted emails to a comma-delimited
    // list of user_ids.  We should be careful to keep this
    // consistent with hash_util.decode_operand.
    return "#narrow/pm-with/" + user_ids_string + '-group';
};

exports.by_conversation_and_time_uri = function (message, is_absolute_url) {
    var absolute_url = "";
    if (is_absolute_url) {
        absolute_url = window.location.protocol + "//" +
            window.location.host + "/" + window.location.pathname.split('/')[1];
    }
    if (message.type === "stream") {
        return absolute_url + "#narrow/stream/" +
            exports.encode_stream_name(message.stream) +
            "/subject/" + exports.encodeHashComponent(message.subject) +
            "/near/" + exports.encodeHashComponent(message.id);
    }

    // Include your own email in this URI if it's not there already
    var all_emails = message.reply_to;
    if (all_emails.indexOf(people.my_current_email()) === -1) {
        all_emails += "," + people.my_current_email();
    }
    return absolute_url + "#narrow/pm-with/" +
        exports.encodeHashComponent(all_emails) +
        "/near/" + exports.encodeHashComponent(message.id);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = hash_util;
}
window.hash_util = hash_util;
