/*
    We hand selected the following emojis a few years
    ago to be given extra precedence in our typeahead
    algorithms and emoji picker UIs.  We call them "popular"
    emojis for historical reasons, although we've never
    technically measured their popularity (and any
    results now would be biased in favor of the ones
    below, since they've easier to submit).  Nonetheless, it
    is often convenient to quickly find these.  We can
    adjust this list over time; we just need to make
    sure it works well with the emoji picker's layout
    if you increase the number of them.

    For typeahead we'll favor any of these as long as
    the emoji code matches.  For example, we'll show the
    emoji with code 1f44d at the top of your suggestions
    whether you type "+" as a prefix for "+1"
    or "th" as a prefix for "thumbs up".
*/
export const popular_emojis = [
    "1f44d", // +1
    "1f389", // tada
    "1f642", // smile
    "2764", // heart
    "1f6e0", // working_on_it
    "1f419", // octopus
];

const unicode_marks = /\p{M}/gu;

type Emoji =
    | {
          emoji_name: string;
          reaction_type: "realm_emoji" | "zulip_extra_emoji";
          is_realm_emoji: true;
      }
    | UnicodeEmoji;

// emoji_code is only available for unicode emojis.
type UnicodeEmoji = {
    emoji_name: string;
    emoji_code: string;
    reaction_type: "unicode_emoji";
    is_realm_emoji: false;
};

export function remove_diacritics(s: string): string {
    return s.normalize("NFKD").replace(unicode_marks, "");
}

// This function attempts to match a query with a source text.
// * query is the user-entered search query
// * source_str is the string we're matching in, e.g. a user's name
// * split_char is the separator for this syntax (e.g. ' ').
export function query_matches_string(
    query: string,
    source_str: string,
    split_char: string,
): boolean {
    source_str = source_str.toLowerCase();
    source_str = remove_diacritics(source_str);

    if (!query.includes(split_char)) {
        // If query is a single token (doesn't contain a separator),
        // the match can be anywhere in the string.
        return source_str.includes(query);
    }

    // If there is a separator character in the query, then we
    // require the match to start at the start of a token.
    // (E.g. for 'ab cd ef', query could be 'ab c' or 'cd ef',
    // but not 'b cd ef'.)
    return source_str.startsWith(query) || source_str.includes(split_char + query);
}

function clean_query(query: string): string {
    query = remove_diacritics(query);
    // When `abc ` with a space at the end is typed in
    // a content-editable widget such as the composebox
    // direct message section, the space at the end was
    // a `no break-space (U+00A0)` instead of `space (U+0020)`,
    // which lead to no matches in those cases.
    query = query.replace(/\u00A0/g, " ");

    return query;
}

export function clean_query_lowercase(query: string): string {
    query = query.toLowerCase();
    query = clean_query(query);
    return query;
}

export const parse_unicode_emoji_code = (code: string): string =>
    code
        .split("-")
        .map((hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
        .join("");

export function get_emoji_matcher(query: string): (emoji: Emoji) => boolean {
    // replace spaces with underscores for emoji matching
    query = query.replace(/ /g, "_");
    query = clean_query_lowercase(query);

    return function (emoji) {
        const matches_emoji_literal =
            emoji.reaction_type === "unicode_emoji" &&
            parse_unicode_emoji_code(emoji.emoji_code) === query;
        return matches_emoji_literal || query_matches_string(query, emoji.emoji_name, "_");
    };
}

export function triage<T>(
    query: string,
    objs: T[],
    get_item: (x: T) => string,
    sorting_comparator?: () => number,
): {matches: T[]; rest: T[]} {
    /*
        We split objs into four groups:

            - entire string exact match
            - match prefix exactly with `query`
            - match prefix case-insensitively
            - other

        Then we concat the first three groups into
        `matches` and then call the rest `rest`.
    */

    const exactMatch = [];
    const beginswithCaseSensitive = [];
    const beginswithCaseInsensitive = [];
    const noMatch = [];
    const lowerQuery = query ? query.toLowerCase() : "";

    for (const obj of objs) {
        const item = get_item(obj);
        const lowerItem = item.toLowerCase();

        if (lowerItem === lowerQuery) {
            exactMatch.push(obj);
        } else if (item.startsWith(query)) {
            beginswithCaseSensitive.push(obj);
        } else if (lowerItem.startsWith(lowerQuery)) {
            beginswithCaseInsensitive.push(obj);
        } else {
            noMatch.push(obj);
        }
    }

    if (sorting_comparator) {
        const non_exact_sorted_matches = [
            ...beginswithCaseSensitive,
            ...beginswithCaseInsensitive,
        ].sort(sorting_comparator);
        return {
            matches: [...exactMatch, ...non_exact_sorted_matches],
            rest: noMatch.sort(sorting_comparator),
        };
    }
    return {
        matches: [...exactMatch, ...beginswithCaseSensitive, ...beginswithCaseInsensitive],
        rest: noMatch,
    };
}

export function sort_emojis<T extends Emoji>(objs: T[], query: string): T[] {
    // replace spaces with underscores for emoji matching
    query = query.replace(/ /g, "_");
    query = query.toLowerCase();

    function decent_match(name: string): boolean {
        const pieces = name.toLowerCase().split("_");
        return pieces.some((piece) => piece.startsWith(query));
    }

    const popular_set = new Set(popular_emojis);

    function is_popular(obj: Emoji): boolean {
        return (
            obj.reaction_type === "unicode_emoji" &&
            popular_set.has(obj.emoji_code) &&
            decent_match(obj.emoji_name)
        );
    }

    const realm_emoji_names = new Set(
        objs.filter((obj) => obj.is_realm_emoji).map((obj) => obj.emoji_name),
    );

    const popular_emoji_matches = objs.filter((obj) => is_popular(obj));
    const others = objs.filter((obj) => !is_popular(obj));

    const triage_results = triage(query, others, (x) => x.emoji_name);

    function prioritise_realm_emojis(emojis: T[]): T[] {
        return [
            ...emojis.filter((emoji) => emoji.is_realm_emoji),
            ...emojis.filter((emoji) => !emoji.is_realm_emoji),
        ];
    }

    const sorted_results_with_possible_duplicates = [
        ...popular_emoji_matches,
        ...prioritise_realm_emojis(triage_results.matches),
        ...prioritise_realm_emojis(triage_results.rest),
    ];
    // remove unicode emojis with same code but different names
    // and unicode emojis overridden by realm emojis with same names
    const unicode_emoji_codes = new Set();
    const sorted_unique_results: T[] = [];
    for (const emoji of sorted_results_with_possible_duplicates) {
        if (emoji.reaction_type !== "unicode_emoji") {
            sorted_unique_results.push(emoji);
        } else if (
            !unicode_emoji_codes.has(emoji.emoji_code) &&
            !realm_emoji_names.has(emoji.emoji_name)
        ) {
            unicode_emoji_codes.add(emoji.emoji_code);
            sorted_unique_results.push(emoji);
        }
    }

    return sorted_unique_results;
}
