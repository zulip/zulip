import _ from "lodash";

// We will get actual values when we get initialized.
let emoji_codes = {};

// `emojis_by_name` is the central data source that is supposed to be
// used by every widget in the webapp for gathering data for displaying
// emojis. Emoji picker uses this data to derive data for its own use.
export const emojis_by_name = new Map();

export const all_realm_emojis = new Map();
export const active_realm_emojis = new Map();

const default_emoji_aliases = new Map();

// For legacy reasons we track server_realm_emoji_data,
// since our settings code builds off that format.  We
// should move it to use all_realm_emojis, which requires
// adding author_id here and then changing the settings code
// in a slightly non-trivial way.
let server_realm_emoji_data = {};

// We really want to deprecate this, too.
export function get_server_realm_emoji_data() {
    return server_realm_emoji_data;
}

let emoticon_translations = [];

function build_emoticon_translations() {
    /*

    Build a data structure that looks like something
    like this:

    [
        { regex: /(\:\))/g, replacement_text: ':smile:' },
        { regex: /(\(\:)/g, replacement_text: ':smile:' },
        { regex: /(\:\/)/g, replacement_text: ':confused:' },
        { regex: /(<3)/g, replacement_text: ':heart:' },
        { regex: /(\:\()/g, replacement_text: ':frown:' },
        { regex: /(\:\|)/g, replacement_text: ':expressionless:' }
    ]

        We build up this list of ~6 emoticon translations
        even if page_params.translate_emoticons is false, since
        that setting can be flipped via live update events.
        On the other hand, we assume that emoticon_conversions
        won't change until the next reload, which is fine for
        now (and we want to avoid creating new regexes on
        every new message).
    */

    const translations = [];
    for (const [emoticon, replacement_text] of Object.entries(emoji_codes.emoticon_conversions)) {
        const regex = new RegExp("(" + _.escapeRegExp(emoticon) + ")", "g");

        translations.push({
            regex,
            replacement_text,
        });
    }

    emoticon_translations = translations;
}

const zulip_emoji = {
    id: "zulip",
    emoji_name: "zulip",
    emoji_url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
    is_realm_emoji: true,
    deactivated: false,
};

export function get_emoji_name(codepoint) {
    // get_emoji_name('1f384') === 'holiday_tree'
    if (Object.prototype.hasOwnProperty.call(emoji_codes.codepoint_to_name, codepoint)) {
        return emoji_codes.codepoint_to_name[codepoint];
    }
    return undefined;
}

export function get_emoji_codepoint(emoji_name) {
    // get_emoji_codepoint('avocado') === '1f951'
    if (Object.prototype.hasOwnProperty.call(emoji_codes.name_to_codepoint, emoji_name)) {
        return emoji_codes.name_to_codepoint[emoji_name];
    }
    return undefined;
}

export function get_realm_emoji_url(emoji_name) {
    // If the emoji name is a realm emoji, returns the URL for it.
    // Returns undefined for unicode emoji.
    // get_realm_emoji_url('shrug') === '/user_avatars/2/emoji/images/31.png'

    const data = active_realm_emojis.get(emoji_name);

    if (!data) {
        // Not all emojis have urls, plus the user
        // may have hand-typed an invalid emoji.
        // The caller can check the result for falsiness
        // and then try alternate ways of parsing the
        // emoji (in the case of Markdown) or just do
        // whatever makes sense for the caller.
        return undefined;
    }

    return data.emoji_url;
}

export function build_emoji_data(realm_emojis) {
    emojis_by_name.clear();
    for (const [realm_emoji_name, realm_emoji] of realm_emojis) {
        const emoji_dict = {
            name: realm_emoji_name,
            display_name: realm_emoji_name,
            aliases: [realm_emoji_name],
            is_realm_emoji: true,
            url: realm_emoji.emoji_url,
            has_reacted: false,
        };
        emojis_by_name.set(realm_emoji_name, emoji_dict);
    }

    for (const codepoints of Object.values(emoji_codes.emoji_catalog)) {
        for (const codepoint of codepoints) {
            const emoji_name = get_emoji_name(codepoint);
            if (emoji_name !== undefined && !emojis_by_name.has(emoji_name)) {
                const emoji_dict = {
                    name: emoji_name,
                    display_name: emoji_name,
                    aliases: default_emoji_aliases.get(codepoint),
                    is_realm_emoji: false,
                    emoji_code: codepoint,
                    has_reacted: false,
                };
                emojis_by_name.set(emoji_name, emoji_dict);
            }
        }
    }
}

export function update_emojis(realm_emojis) {
    // The settings code still works with the
    // server format of the data.
    server_realm_emoji_data = realm_emojis;

    // all_realm_emojis is emptied before adding the realm-specific emoji
    // to it. This makes sure that in case of deletion, the deleted realm_emojis
    // don't persist in active_realm_emojis.
    all_realm_emojis.clear();
    active_realm_emojis.clear();

    for (const data of Object.values(realm_emojis)) {
        all_realm_emojis.set(data.id, {
            id: data.id,
            emoji_name: data.name,
            emoji_url: data.source_url,
            deactivated: data.deactivated,
        });
        if (data.deactivated !== true) {
            active_realm_emojis.set(data.name, {
                id: data.id,
                emoji_name: data.name,
                emoji_url: data.source_url,
            });
        }
    }
    // Add the Zulip emoji to the realm emojis list
    all_realm_emojis.set("zulip", zulip_emoji);
    active_realm_emojis.set("zulip", zulip_emoji);

    build_emoji_data(active_realm_emojis);
}

export function initialize(params) {
    emoji_codes = params.emoji_codes;

    build_emoticon_translations();

    for (const value of emoji_codes.names) {
        const base_name = get_emoji_codepoint(value);

        if (default_emoji_aliases.has(base_name)) {
            default_emoji_aliases.get(base_name).push(value);
        } else {
            default_emoji_aliases.set(base_name, [value]);
        }
    }

    update_emojis(params.realm_emoji);
}

export function get_canonical_name(emoji_name) {
    if (active_realm_emojis.has(emoji_name)) {
        return emoji_name;
    }
    const codepoint = get_emoji_codepoint(emoji_name);
    if (codepoint === undefined) {
        // Our caller needs to handle this possibility.
        return undefined;
    }

    return get_emoji_name(codepoint);
}

export function get_emoticon_translations() {
    return emoticon_translations;
}
