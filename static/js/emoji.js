import _ from "lodash";

// We will get actual values when we get initialized.
let emoji_codes = {};

// `emojis_by_name` is the central data source that is supposed to be
// used by every widget in the web app for gathering data for displaying
// emojis. Emoji picker uses this data to derive data for its own use.
export let emojis_by_name = new Map();

export const all_realm_emojis = new Map();
export const active_realm_emojis = new Map();
export const deactivated_emoji_name_to_code = new Map();

let default_emoji_aliases = new Map();

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

function build_emoticon_translations({emoticon_conversions}) {
    /*

    Please keep this as a pure function so that we can
    eventually share this code with the mobile codebase.

    Build a data structure that looks like something
    like this:

    [
        { regex: /(\:\))/g, replacement_text: ':smile:' },
        { regex: /(\(\:)/g, replacement_text: ':smile:' },
        { regex: /(\:\/)/g, replacement_text: ':confused:' },
        { regex: /(<3)/g, replacement_text: ':heart:' },
        { regex: /(\:\()/g, replacement_text: ':frown:' },
        { regex: /(\:\|)/g, replacement_text: ':expressionless:' },
        ....
    ]

        We build up this list of ~12 emoticon translations even
        if user_settings.translate_emoticons is false, since
        that setting can be flipped via live update events.
        On the other hand, we assume that emoticon_conversions
        won't change until the next reload, which is fine for
        now (and we want to avoid creating new regexes on
        every new message).
    */

    const translations = [];
    for (const [emoticon, replacement_text] of Object.entries(emoticon_conversions)) {
        const regex = new RegExp("(" + _.escapeRegExp(emoticon) + ")", "g");

        translations.push({
            regex,
            replacement_text,
        });
    }

    return translations;
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
    if (Object.hasOwn(emoji_codes.codepoint_to_name, codepoint)) {
        return emoji_codes.codepoint_to_name[codepoint];
    }
    return undefined;
}

export function get_emoji_codepoint(emoji_name) {
    // get_emoji_codepoint('avocado') === '1f951'
    if (Object.hasOwn(emoji_codes.name_to_codepoint, emoji_name)) {
        return emoji_codes.name_to_codepoint[emoji_name];
    }
    return undefined;
}

export function get_realm_emoji_url(emoji_name) {
    // If the emoji name is a realm emoji, returns the URL for it.
    // Returns undefined for Unicode emoji.
    // get_realm_emoji_url('shrug') === '/user_avatars/2/emoji/images/31.png'

    const data = active_realm_emojis.get(emoji_name);

    if (!data) {
        // Not all emojis have URLs, plus the user
        // may have hand-typed an invalid emoji.
        // The caller can check the result for falsiness
        // and then try alternate ways of parsing the
        // emoji (in the case of Markdown) or just do
        // whatever makes sense for the caller.
        return undefined;
    }

    return data.emoji_url;
}

function build_emojis_by_name({
    realm_emojis,
    emoji_catalog,
    get_emoji_name,
    default_emoji_aliases,
}) {
    // Please keep this as a pure function so that we can
    // eventually share this code with the mobile codebase.
    const map = new Map();

    for (const codepoints of Object.values(emoji_catalog)) {
        for (const codepoint of codepoints) {
            const emoji_name = get_emoji_name(codepoint);
            if (emoji_name !== undefined) {
                const emoji_dict = {
                    name: emoji_name,
                    display_name: emoji_name,
                    aliases: default_emoji_aliases.get(codepoint),
                    is_realm_emoji: false,
                    emoji_code: codepoint,
                    has_reacted: false,
                };
                // We may later get overridden by a realm emoji.
                map.set(emoji_name, emoji_dict);
            }
        }
    }

    for (const [realm_emoji_name, realm_emoji] of realm_emojis) {
        const emoji_dict = {
            name: realm_emoji_name,
            display_name: realm_emoji_name,
            aliases: [realm_emoji_name],
            is_realm_emoji: true,
            url: realm_emoji.emoji_url,
            has_reacted: false,
        };

        // We want the realm emoji to overwrite any existing entry in this map.
        map.set(realm_emoji_name, emoji_dict);
    }

    return map;
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
            still_url: data.still_url,
            deactivated: data.deactivated,
        });
        if (data.deactivated !== true) {
            active_realm_emojis.set(data.name, {
                id: data.id,
                emoji_name: data.name,
                emoji_url: data.source_url,
                still_url: data.still_url,
            });
        }
    }

    // Add the special Zulip emoji as though it were a realm emoji.

    // The Zulip emoji is the only emoji that uses a string ("zulip")
    // as its ID. All other emoji use numeric IDs. This special case
    // is confusing; ideally we'd convert the Zulip emoji to be
    // implemented using the RealmEmoji infrastructure.
    all_realm_emojis.set("zulip", zulip_emoji);

    // here "zulip" is an emoji name, which is fine.
    active_realm_emojis.set("zulip", zulip_emoji);

    emojis_by_name = build_emojis_by_name({
        realm_emojis: active_realm_emojis,
        emoji_catalog: emoji_codes.emoji_catalog,
        get_emoji_name,
        default_emoji_aliases,
    });
}

// This function will provide required parameters that would
// need by template to render an emoji.
export function get_emoji_details_by_name(emoji_name) {
    // To call this function you must pass an emoji name.
    if (!emoji_name) {
        throw new Error("Emoji name must be passed.");
    }

    const emoji_info = {emoji_name};

    if (active_realm_emojis.has(emoji_name)) {
        if (emoji_name === "zulip") {
            emoji_info.reaction_type = "zulip_extra_emoji";
        } else {
            emoji_info.reaction_type = "realm_emoji";
        }
        const emoji_code_info = active_realm_emojis.get(emoji_name);
        emoji_info.emoji_code = emoji_code_info.id;
        emoji_info.url = emoji_code_info.emoji_url;
        if (emoji_code_info.still_url) {
            emoji_info.still_url = emoji_code_info.still_url;
        }
    } else {
        const codepoint = get_emoji_codepoint(emoji_name);
        if (codepoint === undefined) {
            throw new Error("Bad emoji name: " + emoji_name);
        }
        emoji_info.reaction_type = "unicode_emoji";
        emoji_info.emoji_code = codepoint;
    }
    return emoji_info;
}

export function get_emoji_details_for_rendering(opts) {
    if (!opts.emoji_name || !opts.emoji_code || !opts.reaction_type) {
        throw new Error("Invalid params.");
    }

    if (opts.reaction_type !== "unicode_emoji") {
        const realm_emoji = all_realm_emojis.get(opts.emoji_code);
        if (!realm_emoji) {
            throw new Error(`Cannot find realm emoji for code '${opts.emoji_code}'.`);
        }
        return {
            url: realm_emoji.emoji_url,
            still_url: realm_emoji.still_url,
            emoji_name: opts.emoji_name,
            emoji_code: opts.emoji_code,
            reaction_type: opts.reaction_type,
        };
    }
    // else
    return {
        emoji_name: opts.emoji_name,
        emoji_code: opts.emoji_code,
        reaction_type: opts.reaction_type,
    };
}

function build_default_emoji_aliases({names, get_emoji_codepoint}) {
    // Please keep this as a pure function so that we can
    // eventually share this code with the mobile codebase.

    // Create a map of codepoint -> names
    const map = new Map();

    for (const name of names) {
        const base_name = get_emoji_codepoint(name);

        if (map.has(base_name)) {
            map.get(base_name).push(name);
        } else {
            map.set(base_name, [name]);
        }
    }

    return map;
}

export function initialize(params) {
    emoji_codes = params.emoji_codes;

    emoticon_translations = build_emoticon_translations({
        emoticon_conversions: emoji_codes.emoticon_conversions,
    });

    default_emoji_aliases = build_default_emoji_aliases({
        names: emoji_codes.names,
        get_emoji_codepoint,
    });

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
