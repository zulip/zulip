var emoji = (function () {

var exports = {};

exports.emojis = [];
exports.all_realm_emojis = {};
exports.active_realm_emojis = {};
exports.emojis_by_name = {};
exports.emojis_name_to_css_class = {};
exports.default_emoji_aliases = {};

var default_emojis = [];

var zulip_emoji = {
    emoji_name: 'zulip',
    emoji_url: '/static/generated/emoji/images/emoji/unicode/zulip.png',
    is_realm_emoji: true,
    deactivated: false,
};

// Emoticons, and which emoji they should become (without colons). Duplicate
// emoji are allowed. Changes here should be mimicked in `zerver/lib/emoji.py`.
var EMOTICON_CONVERSIONS = {
    ':)': 'smiley',
    '(:': 'smiley',
    ':(': 'slightly_frowning_face',
    '<3': 'heart',
    ':|': 'expressionless',
    ':/': 'confused',
};

exports.update_emojis = function update_emojis(realm_emojis) {
    // exports.all_realm_emojis is emptied before adding the realm-specific emoji to it.
    // This makes sure that in case of deletion, the deleted realm_emojis don't
    // persist in exports.all_realm_emojis or exports.active_realm_emojis.
    exports.all_realm_emojis = {};
    exports.active_realm_emojis = {};

    // Copy the default emoji list and add realm-specific emoji to it
    exports.emojis = default_emojis.slice(0);
    _.each(realm_emojis, function (data, name) {
        exports.all_realm_emojis[name] = {emoji_name: name,
                                          emoji_url: data.source_url,
                                          deactivated: data.deactivated};
        if (data.deactivated !== true) {
            // export.emojis are used in composebox autocomplete. This condition makes sure
            // that deactivated emojis don't appear in the autocomplete.
            exports.emojis.push({emoji_name: name,
                                 emoji_url: data.source_url,
                                 is_realm_emoji: true});
            exports.active_realm_emojis[name] = {emoji_name: name, emoji_url: data.source_url};
        }
    });
    // Add the Zulip emoji to the realm emojis list
    exports.emojis.push(zulip_emoji);
    exports.all_realm_emojis.zulip = zulip_emoji;
    exports.active_realm_emojis.zulip = zulip_emoji;

    exports.emojis_by_name = {};
    exports.emojis_name_to_css_class = {};
    _.each(default_emojis, function (emoji) {
        var css_class = emoji_codes.name_to_codepoint[emoji.emoji_name];
        exports.emojis_name_to_css_class[emoji.emoji_name] = css_class;
        exports.emojis_by_name[emoji.emoji_name] = emoji.emoji_url;
    });
};

exports.initialize = function initialize() {

    _.each(emoji_codes.names, function (value) {
        var base_name = emoji_codes.name_to_codepoint[value];
        default_emojis.push({emoji_name: value,
                             codepoint: emoji_codes.name_to_codepoint[value]});

        if (exports.default_emoji_aliases.hasOwnProperty(base_name)) {
            exports.default_emoji_aliases[base_name].push(value);
        } else {
            exports.default_emoji_aliases[base_name] = [value];
        }
    });

    exports.update_emojis(page_params.realm_emoji);

    // Load the sprite image in the background so that the browser
    // can cache it for later use.
    var sprite = new Image();
    sprite.src = '/static/generated/emoji/sheet_' + page_params.emojiset + '_32.png';
};

exports.build_emoji_upload_widget = function () {

    var get_file_input = function () {
        return $('#emoji_file_input');
    };

    var file_name_field = $('#emoji-file-name');
    var input_error = $('#emoji_file_input_error');
    var clear_button = $('#emoji_image_clear_button');
    var upload_button = $('#emoji_upload_button');

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button
    );
};

exports.get_canonical_name = function (emoji_name) {
    if (exports.active_realm_emojis.hasOwnProperty(emoji_name)) {
        return emoji_name;
    }
    if (!emoji_codes.name_to_codepoint.hasOwnProperty(emoji_name)) {
        blueslip.error("Invalid emoji name: " + emoji_name);
        return;
    }
    var codepoint = emoji_codes.name_to_codepoint[emoji_name];

    return emoji_codes.codepoint_to_name[codepoint];
};

// Translates emoticons in a string to their colon syntax.
exports.translate_emoticons_to_names = function translate_emoticons_to_names(text) {
    var translated = text;

    for (var emoticon in EMOTICON_CONVERSIONS) {
        if (EMOTICON_CONVERSIONS.hasOwnProperty(emoticon)) {
            var emoticon_reg_ex = new RegExp(util.escape_regexp(emoticon), "g");
            translated = translated.replace(
                emoticon_reg_ex,
                ':' + EMOTICON_CONVERSIONS[emoticon] + ':');
        }
    }

    return translated;
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = emoji;
}
