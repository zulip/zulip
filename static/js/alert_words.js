var alert_words = (function () {

var exports = {};

exports.words = page_params.alert_words;

// escape_user_regex taken from jquery-ui/autocomplete.js,
// licensed under MIT license.
function escape_user_regex(value) {
    return value.replace(/[\-\[\]{}()*+?.,\\\^$|#\s]/g, "\\$&");
}

var find_href_backwards = /href=['"][\w:\/\.]+$/;
var find_title_backwards = /title=['"][\w:\/\.]+$/;

exports.process_message = function (message) {
    if (!exports.notifies(message)) {
        return;
    }

    _.each(exports.words, function (word) {
        var clean = escape_user_regex(word);
        var before_punctuation = '\\s|^|>|[\\(\\".,\';\\[]';
        var after_punctuation = '\\s|$|<|[\\)\\"\\?!:.,\';\\]!]';


        var regex = new RegExp('(' + before_punctuation + ')' +
                               '(' + clean + ')' +
                               '(' + after_punctuation + ')' , 'ig');
        message.content = message.content.replace(regex, function (match, before, word,
                                                                   after, offset, content) {
            // Don't munge URL hrefs
            var pre_match = content.substring(0, offset);
            if (find_href_backwards.exec(pre_match) || find_title_backwards.exec(pre_match)) {
                return before + word + after;
            }
            return before + "<span class='alert-word'>" + word + "</span>" + after;
        });
    });
};

exports.notifies = function (message) {
    return !people.is_current_user(message.sender_email) && message.alerted;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = alert_words;
}
