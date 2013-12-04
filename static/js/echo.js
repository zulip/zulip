var echo = (function () {

var exports = {};

// Regexes that match some of our common bugdown markup
var bugdown_re = [
                    /(?::[^:\s]+:)(?!\w)/, // Emoji
                    // Inline image previews, check for contiguous chars ending in image suffix
                    // To keep the below regexes simple, split them out for the end-of-message case
                    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)\s+/m,
                    /[^\s]*(?:\.bmp|\.gif|\.jpg|\.jpeg|\.png|\.webp)$/m,
                    // Twitter and youtube links are given previews
                    /[^\s]*(?:twitter|youtube).com\/[^\s]*/,
                    // Gravatars are inlined as well
                    /!avatar\([^)]+\)/,
                    /!gravatar\([^)]+\)/,
                    // User mentions
                    /\s+@\*\*[^\*]+\*\*/m
                  ];

exports.contains_bugdown = function contains_bugdown(content) {
    // Try to guess whether or not a message has bugdown in it
    // If it doesn't, we can immediately render it client-side
    var markedup = _.find(bugdown_re, function (re) {
        return re.test(content);
    });
    return markedup !== undefined;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = echo;
}
