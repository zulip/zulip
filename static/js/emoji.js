const util = require("./util");
const emoji_codes = require("../generated/emoji/emoji_codes.json");

// `emojis_by_name` is the central data source that is supposed to be
// used by every widget in the webapp for gathering data for displaying
// emojis. Emoji picker uses this data to derive data for its own use.
exports.emojis_by_name = new Map();

exports.all_realm_emojis = new Map();
exports.active_realm_emojis = new Map();
exports.default_emoji_aliases = new Map();

const zulip_emoji = {
    id: 'zulip',
    emoji_name: 'zulip',
    emoji_url: '/static/generated/emoji/images/emoji/unicode/zulip.png',
    is_realm_emoji: true,
    deactivated: false,
};

exports.update_emojis = function update_emojis(realm_emojis) {
    // exports.all_realm_emojis is emptied before adding the realm-specific emoji
    // to it. This makes sure that in case of deletion, the deleted realm_emojis
    // don't persist in exports.active_realm_emojis.
    exports.all_realm_emojis.clear();
    exports.active_realm_emojis.clear();

    for (const data of Object.values(realm_emojis)) {
        exports.all_realm_emojis.set(data.id, {
            id: data.id,
            emoji_name: data.name,
            emoji_url: data.source_url,
            deactivated: data.deactivated,
        });
        if (data.deactivated !== true) {
            exports.active_realm_emojis.set(data.name, {
                id: data.id,
                emoji_name: data.name,
                emoji_url: data.source_url,
            });
        }
    }
    // Add the Zulip emoji to the realm emojis list
    exports.all_realm_emojis.set("zulip", zulip_emoji);
    exports.active_realm_emojis.set("zulip", zulip_emoji);

    exports.build_emoji_data(exports.active_realm_emojis);
};

exports.initialize = function initialize() {
    for (const value of emoji_codes.names) {
        const base_name = emoji_codes.name_to_codepoint[value];

        if (exports.default_emoji_aliases.has(base_name)) {
            exports.default_emoji_aliases.get(base_name).push(value);
        } else {
            exports.default_emoji_aliases.set(base_name, [value]);
        }
    }

    exports.update_emojis(page_params.realm_emoji);

    let emojiset = page_params.emojiset;
    if (page_params.emojiset === 'text') {
        // If the current emojiset is `text`, then we fallback to the
        // `google` emojiset on the backend (see zerver/views/home.py)
        // for displaying emojis in emoji picker and composebox
        // typeahead. This logic ensures that we do sprite sheet
        // prefetching for that case.
        emojiset = 'google-blob';
    }
    // Load the sprite image and octopus image in the background, so
    // that the browser will cache it for later use.
    const sprite = new Image();
    sprite.src = '/static/generated/emoji/sheet-' + emojiset + '-64.png';
    const octopus_image = new Image();
    octopus_image.src = '/static/generated/emoji/images-' + emojiset + '-64/1f419.png';
};

exports.build_emoji_data = function (realm_emojis) {
    exports.emojis_by_name.clear();
    for (const [realm_emoji_name, realm_emoji] of realm_emojis) {
        const emoji_dict = {
            name: realm_emoji_name,
            display_name: realm_emoji_name,
            aliases: [realm_emoji_name],
            is_realm_emoji: true,
            url: realm_emoji.emoji_url,
            has_reacted: false,
        };
        exports.emojis_by_name.set(realm_emoji_name, emoji_dict);
    }

    for (const codepoints of Object.values(emoji_codes.emoji_catalog)) {
        for (const codepoint of codepoints) {
            if (emoji_codes.codepoint_to_name.hasOwnProperty(codepoint)) {
                const emoji_name = emoji_codes.codepoint_to_name[codepoint];
                if (!exports.emojis_by_name.has(emoji_name)) {
                    const emoji_dict = {
                        name: emoji_name,
                        display_name: emoji_name,
                        aliases: exports.default_emoji_aliases.get(codepoint),
                        is_realm_emoji: false,
                        emoji_code: codepoint,
                        has_reacted: false,
                    };
                    exports.emojis_by_name.set(emoji_name, emoji_dict);
                }
            }
        }
    }
};

exports.build_emoji_upload_widget = function () {

    const get_file_input = function () {
        return $('#emoji_file_input');
    };

    const file_name_field = $('#emoji-file-name');
    const input_error = $('#emoji_file_input_error');
    const clear_button = $('#emoji_image_clear_button');
    const upload_button = $('#emoji_upload_button');

    return upload_widget.build_widget(
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button
    );
};

exports.get_canonical_name = function (emoji_name) {
    if (exports.active_realm_emojis.has(emoji_name)) {
        return emoji_name;
    }
    if (!emoji_codes.name_to_codepoint.hasOwnProperty(emoji_name)) {
        blueslip.error("Invalid emoji name: " + emoji_name);
        return;
    }
    const codepoint = emoji_codes.name_to_codepoint[emoji_name];

    return emoji_codes.codepoint_to_name[codepoint];
};

// Translates emoticons in a string to their colon syntax.
exports.translate_emoticons_to_names = function translate_emoticons_to_names(text) {
    let translated = text;
    let replacement_text;
    const terminal_symbols = ',.;?!()[] "\'\n\t'; // From composebox_typeahead
    const symbols_except_space = terminal_symbols.replace(' ', '');

    const emoticon_replacer = function (match, g1, offset, str) {
        const prev_char = str[offset - 1];
        const next_char = str[offset + match.length];

        const symbol_at_start = terminal_symbols.includes(prev_char);
        const symbol_at_end = terminal_symbols.includes(next_char);
        const non_space_at_start = symbols_except_space.includes(prev_char);
        const non_space_at_end = symbols_except_space.includes(next_char);
        const valid_start = symbol_at_start || offset === 0;
        const valid_end = symbol_at_end || offset === str.length - match.length;

        if (non_space_at_start && non_space_at_end) { // Hello!:)?
            return match;
        }
        if (valid_start && valid_end) {
            return replacement_text;
        }
        return match;
    };

    for (const emoticon in emoji_codes.emoticon_conversions) {
        if (emoji_codes.emoticon_conversions.hasOwnProperty(emoticon)) {
            replacement_text = emoji_codes.emoticon_conversions[emoticon];
            const emoticon_regex = new RegExp('(' + util.escape_regexp(emoticon) + ')', 'g');
            translated = translated.replace(emoticon_regex, emoticon_replacer);
        }
    }

    return translated;
};

window.emoji = exports;
