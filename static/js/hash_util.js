var hash_util = (function () {

var exports = {};

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).
exports.encodeHashComponent = function (str) {
    return encodeURIComponent(str)
        .replace(/\./g, '%2E')
        .replace(/%/g,  '.');
};

exports.encode_operand = function (operator, operand) {
    if ((operator === 'group-pm-with') || (operator === 'pm-with') || (operator === 'sender')) {
        var slug = people.emails_to_slug(operand);
        if (slug) {
            return slug;
        }
    }

    return exports.encodeHashComponent(operand);
};

exports.decodeHashComponent = function (str) {
    return decodeURIComponent(str.replace(/\./g, '%'));
};

exports.decode_operand = function (operator, operand) {
    if ((operator === 'group-pm-with') || (operator === 'pm-with') || (operator === 'sender')) {
        var emails = people.slug_to_emails(operand);
        if (emails) {
            return emails;
        }
    }

    return exports.decodeHashComponent(operand);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = hash_util;
}
