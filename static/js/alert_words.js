var alert_words = (function () {

var exports = {};

exports.words = page_params.alert_words;

// escape_user_regex taken from jquery-ui/autocomplete.js,
// licensed under MIT license.
function escape_user_regex(value) {
    return value.replace(/[\-\[\]{}()*+?.,\\\^$|#\s]/g, "\\$&");
}

exports.process_message = function (message) {
    if (!feature_flags.alert_words || !exports.notifies(message)) {
        return;
    }

    _.each(exports.words, function (word) {
        var clean = escape_user_regex(word);
        var before_punctuation = '\\s|^|>|[\\(\\"]';
        var after_punctuation = '\\s|$|<|[\\)\\"\\?:.,]';

        var regex = new RegExp('(' + before_punctuation + ')' +
                               '(' + clean + ')' +
                               '(' + after_punctuation + ')' , 'i');
        message.content = message.content.replace(regex, function (match, before, word, after) {
            return before + "<span class='alert-word'>" + word + "</span>" + after;
        });
    });
};

exports.notifies = function (message) {
    return ((message.sender_email !== page_params.email) &&
            (message.flags.indexOf('has_alert_word') > -1));
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = alert_words;
}
