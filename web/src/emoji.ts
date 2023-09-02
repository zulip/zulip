import _ from "lodash";

import * as blueslip from "./blueslip";
import type {User} from "./people";

// This is the data structure that we get from the server on initialization.
export type ServerEmoji = {
    id: number;
    author_id: number;
    deactivated: boolean;
    name: string;
    source_url: string;
    still_url: string | null;

    // Added later in `settings_emoji.ts` when setting up the emoji settings.
    author?: User | null;
};

type RealmEmojiMap = Record<string, ServerEmoji>;

// The data the server provides about unicode emojis.
type ServerUnicodeEmojiData = {
    codepoint_to_name: Record<string, string>;
    name_to_codepoint: Record<string, string>;
    emoji_catalog: Record<string, string[]>;
    emoticon_conversions: Record<string, string>;
    names: string[];
};

type EmojiParams = {
    realm_emoji: RealmEmojiMap;
    emoji_codes: ServerUnicodeEmojiData;
};

type EmoticonTranslation = {
    regex: RegExp;
    replacement_text: string;
};

type RealmEmoji = {
    id: number;
    emoji_name: string;
    emoji_url: string;
    still_url: string | null;
    deactivated: boolean;
};

// Data structure which every widget(like Emoji Picker) in the web app is supposed to use for displaying emojis.
type EmojiDict = {
    name: string;
    display_name: string;
    aliases: string[];
    is_realm_emoji: boolean;
    has_reacted: boolean;
    emoji_code?: string;
    url?: string;
};

// Details needed by template to render an emoji.
export type EmojiRenderingDetails = {
    emoji_name: string;
    reaction_type: string;
    emoji_code: string | number;
    url?: string;
    still_url?: string | null;
};

// We will get actual values when we get initialized.
let emoji_codes: ServerUnicodeEmojiData;

// `emojis_by_name` is the central data source that is supposed to be
// used by every widget in the web app for gathering data for displaying
// emojis. Emoji picker uses this data to derive data for its own use.
export let emojis_by_name = new Map<string, EmojiDict>();
export const all_realm_emojis = new Map<number | string, RealmEmoji | typeof zulip_emoji>();
export const active_realm_emojis = new Map<
    string,
    Omit<RealmEmoji, "deactivated"> | typeof zulip_emoji
>();

let default_emoji_aliases = new Map<string, string[]>();

// For legacy reasons we track server_realm_emoji_data,
// since our settings code builds off that format.  We
// should move it to use all_realm_emojis, which requires
// adding author_id here and then changing the settings code
// in a slightly non-trivial way.
let server_realm_emoji_data: RealmEmojiMap = {};

// We really want to deprecate this, too.
export function get_server_realm_emoji_data(): RealmEmojiMap {
    return server_realm_emoji_data;
}

let emoticon_translations: EmoticonTranslation[] = [];

function build_emoticon_translations({
    emoticon_conversions,
}: Pick<ServerUnicodeEmojiData, "emoticon_conversions">): EmoticonTranslation[] {
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

    const translations: EmoticonTranslation[] = [];
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
    // We don't use a webpack'd URL here, for consistency with the
    // server-side markdown, which doesn't want to render it into the
    // message content.
    emoji_url: "/static/generated/emoji/images/emoji/unicode/zulip.png",
    still_url: null,
    is_realm_emoji: true,
    deactivated: false,
};

export function get_emoji_name(codepoint: string): string | undefined {
    // get_emoji_name('1f384') === 'holiday_tree'
    if (Object.hasOwn(emoji_codes.codepoint_to_name, codepoint)) {
        return emoji_codes.codepoint_to_name[codepoint];
    }
    return undefined;
}

export function get_emoji_codepoint(emoji_name: string): string | undefined {
    // get_emoji_codepoint('avocado') === '1f951'
    if (Object.hasOwn(emoji_codes.name_to_codepoint, emoji_name)) {
        return emoji_codes.name_to_codepoint[emoji_name];
    }
    return undefined;
}

export function get_realm_emoji_url(emoji_name: string): string | undefined {
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
}: {
    realm_emojis: typeof active_realm_emojis;
    emoji_catalog: ServerUnicodeEmojiData["emoji_catalog"];
    get_emoji_name: (codepoint: string) => string | undefined;
    default_emoji_aliases: Map<string, string[]>;
}): Map<string, EmojiDict> {
    // Please keep this as a pure function so that we can
    // eventually share this code with the mobile codebase.
    const map = new Map<string, EmojiDict>();

    for (const codepoints of Object.values(emoji_catalog)) {
        for (const codepoint of codepoints) {
            const emoji_name = get_emoji_name(codepoint);
            if (emoji_name !== undefined) {
                const emoji_dict: EmojiDict = {
                    name: emoji_name,
                    display_name: emoji_name,
                    aliases: default_emoji_aliases.get(codepoint) ?? [],
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
        const emoji_dict: EmojiDict = {
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

export function update_emojis(realm_emojis: RealmEmojiMap): void {
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
        if (!data.deactivated) {
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
export function get_emoji_details_by_name(emoji_name: string): EmojiRenderingDetails {
    // To call this function you must pass an emoji name.
    if (!emoji_name) {
        throw new Error("Emoji name must be passed.");
    }

    if (active_realm_emojis.has(emoji_name)) {
        const emoji_code_info = active_realm_emojis.get(emoji_name)!;
        return {
            emoji_name,
            emoji_code: emoji_code_info.id,
            url: emoji_code_info.emoji_url,
            still_url: emoji_code_info.still_url,
            reaction_type: emoji_name === "zulip" ? "zulip_extra_emoji" : "realm_emoji",
        };
    }

    const codepoint = get_emoji_codepoint(emoji_name);
    if (codepoint === undefined) {
        throw new Error("Bad emoji name: " + emoji_name);
    }

    return {
        emoji_name,
        reaction_type: "unicode_emoji",
        emoji_code: codepoint,
    };
}

export function get_emoji_details_for_rendering(opts: {
    emoji_name: string;
    emoji_code: string | number;
    reaction_type: string;
}): EmojiRenderingDetails {
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

function build_default_emoji_aliases({
    names,
    get_emoji_codepoint,
}: {
    names: string[];
    get_emoji_codepoint: (name: string) => string | undefined;
}): Map<string, string[]> {
    // Please keep this as a pure function so that we can
    // eventually share this code with the mobile codebase.

    // Create a map of codepoint -> names
    const map = new Map<string, string[]>();

    for (const name of names) {
        const base_name = get_emoji_codepoint(name);

        if (base_name === undefined) {
            blueslip.error(`No codepoint for emoji name ${name}`);
            continue;
        }

        if (map.has(base_name)) {
            map.get(base_name)!.push(name);
        } else {
            map.set(base_name, [name]);
        }
    }

    return map;
}

export function initialize(params: EmojiParams): void {
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

export function get_canonical_name(emoji_name: string): string | undefined {
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

export function get_emoticon_translations(): EmoticonTranslation[] {
    return emoticon_translations;
}
