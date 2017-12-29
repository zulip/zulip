var emoji_conversions = (function () {

var exports = {};

var conversions = {
    ":)": ":simple_smile:",
    ":-)": ":simple_smile:",
    ";)": ":wink:",
    ";-)": ":wink:",
    ":(": ":disappointed:",
    ":-(": ":disappointed:",
    ":'(": ":cry:",
    ":'-(": ":cry:",
    ":D": ":smiley:",
    ":-D": ":smiley:",
    "<3": ":heart:"
};

exports.convert_emoji = function (text) {
    for (var i in conversions) {
        text = text.replace(i, conversions[i]);
	}
    return text;
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = emoji_conversions;
}
