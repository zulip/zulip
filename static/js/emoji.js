var emoji = (function () {

var exports = {};

exports.emojis = [];
exports.realm_emojis = {};
exports.emojis_by_name = {};
exports.emojis_name_to_css_class = {};
exports.emojis_by_unicode = {};

var default_emojis = [];
var default_unicode_emojis = [];

emoji_codes.names.push("zulip");
exports.realm_emojis.zulip = {
    emoji_name: 'zulip',
    emoji_url: '/static/generated/emoji/images/emoji/zulip.png',
};

_.each(emoji_codes.names, function (value) {
    default_emojis.push({emoji_name: value, emoji_url: "/static/generated/emoji/images/emoji/" + value + ".png"});
});

_.each(emoji_codes.codepoints, function (value) {
    default_unicode_emojis.push({emoji_name: value, emoji_url: "/static/generated/emoji/images/emoji/unicode/" + value + ".png"});
});

exports.emoji_name_to_css_class = function (emoji_name) {
    if (emoji_name.indexOf("+") >= 0) {
        return emoji_name.replace("+", "");
    }
    return emoji_name;
};

exports.update_emojis = function update_emojis(realm_emojis) {
    // Copy the default emoji list and add realm-specific emoji to it
    exports.emojis = default_emojis.slice(0);
    _.each(realm_emojis, function (data, name) {
        exports.emojis.push({emoji_name: name, emoji_url: data.display_url, is_realm_emoji: true});
        exports.realm_emojis[name] = {emoji_name: name, emoji_url: data.display_url};
    });
    exports.emojis_by_name = {};
    exports.emojis_name_to_css_class = {};
    _.each(exports.emojis, function (emoji) {
        var css_class = exports.emoji_name_to_css_class(emoji.emoji_name);
        exports.emojis_name_to_css_class[emoji.emoji_name] = css_class;
        exports.emojis_by_name[emoji.emoji_name] = emoji.emoji_url;
    });
    exports.emojis_by_unicode = {};
    _.each(default_unicode_emojis, function (emoji) {
        exports.emojis_by_unicode[emoji.emoji_name] = emoji.emoji_url;
    });
};

exports.initialize = function initialize() {
    // Load the sprite image in the background so that the browser
    // can cache it for later use.
    var sprite = new Image();
    sprite.src = '/static/generated/emoji/sprite.png';
};

exports.update_emojis(page_params.realm_emoji);

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = emoji;
}
