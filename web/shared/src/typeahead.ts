import _ from "lodash";

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
    "1f642", // slight_smile
    "2764", // heart
    "1f6e0", // working_on_it
    "1f419", // octopus
];

const unicode_marks = /\p{M}/gu;

export type Emoji =
    | {
          emoji_name: string;
          reaction_type: "realm_emoji" | "zulip_extra_emoji";
          is_realm_emoji: true;
          emoji_url?: string | undefined;
          emoji_code?: undefined;
      }
    | UnicodeEmoji;

// emoji_code is only available for unicode emojis.
type UnicodeEmoji = {
    emoji_name: string;
    emoji_code: string;
    reaction_type: "unicode_emoji";
    is_realm_emoji: false;
    emoji_url?: string | undefined;
};
export type EmojiSuggestion = Emoji & {
    type: "emoji";
};

export type BaseEmoji = {emoji_name: string} & (
    | {is_realm_emoji: false; emoji_code: string}
    | {is_realm_emoji: true; emoji_code?: undefined}
);

export function remove_diacritics(s: string): string {
    return s.normalize("NFKD").replace(unicode_marks, "");
}

export function last_prefix_match(prefix: string, words: string[]): number | null {
    // This function takes in a lexicographically sorted array of `words`,
    // and a `prefix` string. It uses binary search to compute the index
    // of `prefix`'s upper bound, that is, the string immediately after
    // the lexicographically last prefix match of `prefix`. So, the return
    // value is the upper bound minus 1, that is, the last prefix match's
    // index. When no prefix match is found, we return null.
    let left = 0;
    let right = words.length;
    let found = false;
    while (left < right) {
        const mid = Math.floor((left + right) / 2);
        if (words[mid]!.startsWith(prefix)) {
            // Note that left can never be 0 if `found` is true,
            // since it is incremented at least once here.
            left = mid + 1;
            found = true;
        } else if (words[mid]! < prefix) {
            left = mid + 1;
        } else {
            right = mid;
        }
    }
    if (found) {
        return left - 1;
    }
    return null;
}

export function query_matches_string_in_order(
    query: string,
    source_str: string,
    split_char: string,
): boolean {
    query = query.toLowerCase();
    source_str = source_str.toLowerCase();

    const should_remove_diacritics = /^[a-z]+$/.test(query);
    if (should_remove_diacritics) {
        source_str = remove_diacritics(source_str);
    }

    return query_matches_string_in_order_assume_canonicalized(query, source_str, split_char);
}

// This function attempts to match a query in order with a source text.
// * query is the user-entered search query
// * source_str is the string we're matching in, e.g. a user's name
// * split_char is the separator for this syntax (e.g. ' ').
export function query_matches_string_in_order_assume_canonicalized(
    query: string,
    source_str: string,
    split_char: string,
): boolean {
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

// Match the words in the query to the words in the source text, in any order.
//
// The query matches the source if each word in the query can be matched to
// a different word in the source. The order the words appear in the query
// or in the source does not affect the result.
//
// A query word matches a source word if it is a prefix of the source word,
// after both words are converted to lowercase and diacritics are removed.
//
// Returns true if the query matches, and false if not.
//
// * query is the user-entered search query
// * source_str is the string we're matching in, e.g. a user's name
// * split_char is the separator for this syntax (e.g. ' ').
export function query_matches_string_in_any_order(
    query: string,
    source_str: string,
    split_char: string,
): boolean {
    source_str = source_str.toLowerCase();
    source_str = remove_diacritics(source_str);

    query = query.toLowerCase();
    query = remove_diacritics(query);

    const search_words = query.split(split_char).filter(Boolean);
    const source_words = source_str.split(split_char).filter(Boolean);
    if (search_words.length > source_words.length) {
        return false;
    }

    // We go through the search words in reverse lexicographical order, and to select
    // the corresponding source word for each, one by one, we find the lexicographically
    // last possible prefix match and immediately then remove it from consideration for
    // remaining search words.

    // This essentially means that there is no search word lexicographically greater than
    // our current search word (say, q1) which might require the current corresponding source
    // word (as all search words lexicographically greater than it have already been matched)
    // and also that all search words lexicographically smaller than it have the best possible
    // chance for getting matched.

    // This is because if the source word we just removed (say, s1) is the sole match for
    // another search word (say, q2 - obviously lexicographically smaller than q1), this
    // means that either q2 = q1 or that q2 is a prefix of q1. In either case, the final
    // return value of this function should anyway be false, as s1 would be the sole match
    // for q1 too; while we need unique matches for each search word.

    search_words.sort().reverse();
    source_words.sort();
    for (const word of search_words) {
        // `match_index` is the index of the best possible match of `word`.
        const match_index = last_prefix_match(word, source_words);
        if (match_index === null) {
            // We return false if no match was found for `word`.
            return false;
        }
        source_words.splice(match_index, 1);
    }
    return true;
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

export function get_emoji_matcher(query: string): (emoji: EmojiSuggestion) => boolean {
    // replace spaces with underscores for emoji matching
    query = query.replace(/ /g, "_");
    query = clean_query_lowercase(query);

    return function (emoji) {
        const matches_emoji_literal =
            emoji.reaction_type === "unicode_emoji" &&
            parse_unicode_emoji_code(emoji.emoji_code) === query;
        return matches_emoji_literal || query_matches_string_in_order(query, emoji.emoji_name, "_");
    };
}

// space, hyphen, underscore and slash characters are considered word
// boundaries for now, but we might want to consider the characters
// from BEFORE_MENTION_ALLOWED_REGEX in zerver/lib/mention.py later.
export const word_boundary_chars = " _/-";

export function triage_raw_with_multiple_items<T>(
    query: string,
    objs: T[],
    get_items: (x: T) => string[],
): {
    exact_matches: T[];
    begins_with_case_sensitive_matches: T[];
    begins_with_case_insensitive_matches: T[];
    word_boundary_matches: T[];
    no_matches: T[];
} {
    const exact_matches = [];
    const begins_with_case_sensitive_matches = [];
    const begins_with_case_insensitive_matches = [];
    const word_boundary_matches = [];
    const no_matches = [];
    const lower_query = query ? query.toLowerCase() : "";

    const word_boundary_match_regex = new RegExp(
        `[${word_boundary_chars}]${_.escapeRegExp(lower_query)}`,
    );

    for (const obj of objs) {
        const items = get_items(obj);

        const lower_items = items.map((item) => item.toLowerCase());

        if (lower_items.includes(lower_query)) {
            exact_matches.push(obj);
        } else if (items.some((item) => item.startsWith(query))) {
            begins_with_case_sensitive_matches.push(obj);
        } else if (lower_items.some((item) => item.startsWith(lower_query))) {
            begins_with_case_insensitive_matches.push(obj);
        } else if (lower_items.some((item) => word_boundary_match_regex.test(item))) {
            word_boundary_matches.push(obj);
        } else {
            no_matches.push(obj);
        }
    }

    return {
        exact_matches,
        begins_with_case_sensitive_matches,
        begins_with_case_insensitive_matches,
        word_boundary_matches,
        no_matches,
    };
}

export function triage_raw<T>(
    query: string,
    objs: T[],
    get_item: (x: T) => string,
): {
    exact_matches: T[];
    begins_with_case_sensitive_matches: T[];
    begins_with_case_insensitive_matches: T[];
    word_boundary_matches: T[];
    no_matches: T[];
} {
    /*
        We split objs into five groups:

            - entire string exact match
            - match prefix exactly with `query`
            - match prefix case-insensitively
            - match word boundary prefix case-insensitively
            - other

        and return an object of these.
    */
    const exact_matches = [];
    const begins_with_case_sensitive_matches = [];
    const begins_with_case_insensitive_matches = [];
    const word_boundary_matches = [];
    const no_matches = [];
    const lower_query = query ? query.toLowerCase() : "";

    for (const obj of objs) {
        const item = get_item(obj);
        const lower_item = item.toLowerCase();

        if (lower_item === lower_query) {
            exact_matches.push(obj);
        } else if (item.startsWith(query)) {
            begins_with_case_sensitive_matches.push(obj);
        } else if (lower_item.startsWith(lower_query)) {
            begins_with_case_insensitive_matches.push(obj);
        } else if (
            new RegExp(`[${word_boundary_chars}]${_.escapeRegExp(lower_query)}`).test(lower_item)
        ) {
            word_boundary_matches.push(obj);
        } else {
            no_matches.push(obj);
        }
    }

    return {
        exact_matches,
        begins_with_case_sensitive_matches,
        begins_with_case_insensitive_matches,
        word_boundary_matches,
        no_matches,
    };
}

export function triage<T>(
    query: string,
    objs: T[],
    get_item: (x: T) => string,
    sorting_comparator?: (a: T, b: T) => number,
): {matches: T[]; rest: T[]} {
    const {
        exact_matches,
        begins_with_case_sensitive_matches,
        begins_with_case_insensitive_matches,
        word_boundary_matches,
        no_matches,
    } = triage_raw(query, objs, get_item);

    if (sorting_comparator) {
        const beginning_matches_sorted = [
            ...begins_with_case_sensitive_matches,
            ...begins_with_case_insensitive_matches,
        ].sort(sorting_comparator);
        return {
            matches: [
                ...exact_matches.sort(sorting_comparator),
                ...beginning_matches_sorted,
                ...word_boundary_matches.sort(sorting_comparator),
            ],
            rest: no_matches.sort(sorting_comparator),
        };
    }

    return {
        matches: [
            ...exact_matches,
            ...begins_with_case_sensitive_matches,
            ...begins_with_case_insensitive_matches,
            ...word_boundary_matches,
        ],
        rest: no_matches,
    };
}

export function sort_emojis<T extends BaseEmoji>(objs: T[], query: string): T[] {
    // replace spaces with underscores for emoji matching
    query = query.replace(/ /g, "_");
    query = query.toLowerCase();

    function decent_match(name: string): boolean {
        const pieces = name.toLowerCase().split("_");
        return pieces.some((piece) => piece.startsWith(query));
    }

    const popular_set = new Set(popular_emojis);

    function is_popular(obj: BaseEmoji): boolean {
        return (
            !obj.is_realm_emoji && popular_set.has(obj.emoji_code) && decent_match(obj.emoji_name)
        );
    }

    const realm_emoji_names = new Set(
        objs.filter((obj) => obj.is_realm_emoji).map((obj) => obj.emoji_name),
    );

    const perfect_emoji_matches = objs.filter((obj) => obj.emoji_name === query);
    const without_perfect_matches = objs.filter((obj) => obj.emoji_name !== query);

    const popular_emoji_matches = without_perfect_matches.filter((obj) => is_popular(obj));
    const others = without_perfect_matches.filter((obj) => !is_popular(obj));

    const triage_results = triage(query, others, (x) => x.emoji_name);

    function prioritise_realm_emojis(emojis: T[]): T[] {
        return [
            ...emojis.filter((emoji) => emoji.is_realm_emoji),
            ...emojis.filter((emoji) => !emoji.is_realm_emoji),
        ];
    }

    const sorted_results_with_possible_duplicates = [
        ...perfect_emoji_matches,
        ...popular_emoji_matches,
        ...prioritise_realm_emojis(triage_results.matches),
        ...prioritise_realm_emojis(triage_results.rest),
    ];
    // remove unicode emojis with same code but different names
    // and unicode emojis overridden by realm emojis with same names
    const unicode_emoji_codes = new Set();
    const sorted_unique_results: T[] = [];
    for (const emoji of sorted_results_with_possible_duplicates) {
        if (emoji.is_realm_emoji) {
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
