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
    or "th" as a prefix for "thumbs up".  The caveat is
    that other factors still may matter more, such as
    prefix matches trumping "popularity".
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

export function remove_diacritics(s) {
    return s.normalize("NFKD").replace(unicode_marks, "");
}

function query_matches_string(query, source_str, split_char) {
    source_str = remove_diacritics(source_str);

    // If query doesn't contain a separator, we just want an exact
    // match where query is a substring of one of the target characters.
    if (query.indexOf(split_char) > 0) {
        // If there's a whitespace character in the query, then we
        // require a perfect prefix match (e.g. for 'ab cd ef',
        // query needs to be e.g. 'ab c', not 'cd ef' or 'b cd
        // ef', etc.).
        const queries = query.split(split_char);
        const sources = source_str.split(split_char);
        let i;

        for (i = 0; i < queries.length - 1; i += 1) {
            if (sources[i] !== queries[i]) {
                return false;
            }
        }

        // This block is effectively a final iteration of the last
        // loop.  What differs is that for the last word, a
        // partial match at the beginning of the word is OK.
        if (sources[i] === undefined) {
            return false;
        }
        return sources[i].startsWith(queries[i]);
    }

    // For a single token, the match can be anywhere in the string.
    return source_str.includes(query);
}

// This function attempts to match a query with source's attributes.
// * query is the user-entered search query
// * Source is the object we're matching from, e.g. a user object
// * match_attrs are the values associated with the target object that
// the entered string might be trying to match, e.g. for a user
// account, there might be 2 attrs: their full name and their email.
// * split_char is the separator for this syntax (e.g. ' ').
export function query_matches_source_attrs(query, source, match_attrs, split_char) {
    return match_attrs.some((attr) => {
        const source_str = source[attr].toLowerCase();
        return query_matches_string(query, source_str, split_char);
    });
}

function clean_query(query) {
    query = remove_diacritics(query);
    // When `abc ` with a space at the end is typed in a
    // contenteditable widget such as the composebox PM section, the
    // space at the end was a `no break-space (U+00A0)` instead of
    // `space (U+0020)`, which lead to no matches in those cases.
    query = query.replace(/\u00A0/g, " ");

    return query;
}

export function clean_query_lowercase(query) {
    query = query.toLowerCase();
    query = clean_query(query);
    return query;
}

export const parse_unicode_emoji_code = (code) => {
    try {
        return code
            .split("-")
            .map((hex) => String.fromCodePoint(Number.parseInt(hex, 16)))
            .join("");
    } catch {
        // Code could not be parsed, but instead of throwing an exception
        // we return undefined instead of a string.
        return undefined;
    }
};

export function get_emoji_matcher(query) {
    // replaces spaces with underscores for emoji matching
    query = query.replace(/ /g, "_");
    query = clean_query_lowercase(query);

    return function (emoji) {
        const matches_emoji_literal =
            emoji.emoji_code && parse_unicode_emoji_code(emoji.emoji_code) === query;
        return (
            matches_emoji_literal || query_matches_source_attrs(query, emoji, ["emoji_name"], "_")
        );
    };
}

export function triage(query, objs, get_item = (x) => x) {
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
    return {
        matches: exactMatch.concat(beginswithCaseSensitive.concat(beginswithCaseInsensitive)),
        rest: noMatch,
    };
}

export function sort_emojis(objs, query) {
    const lowerQuery = query.toLowerCase();

    function decent_match(name) {
        const pieces = name.toLowerCase().split("_");
        return pieces.some((piece) => piece.startsWith(lowerQuery));
    }

    const popular_set = new Set(popular_emojis);

    function is_popular(obj) {
        return popular_set.has(obj.emoji_code) && decent_match(obj.emoji_name);
    }

    const popular_emoji_matches = objs.filter((obj) => is_popular(obj));
    const others = objs.filter((obj) => !is_popular(obj));

    const triage_results = triage(query, others, (x) => x.emoji_name);

    return [...popular_emoji_matches, ...triage_results.matches, ...triage_results.rest];
}
