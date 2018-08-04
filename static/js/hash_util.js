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


return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = hash_util;
}
window.hash_util = hash_util;
