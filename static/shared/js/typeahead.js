const unicode_marks = /\p{M}/gu;

exports.remove_diacritics = function (s) {
    return s.normalize("NFKD").replace(unicode_marks, "");
};

function query_matches_string(query, source_str, split_char) {
    source_str = exports.remove_diacritics(source_str);

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
    return source_str.indexOf(query) !== -1;
}

// This function attempts to match a query with source's attributes.
// * query is the user-entered search query
// * Source is the object we're matching from, e.g. a user object
// * match_attrs are the values associated with the target object that
// the entered string might be trying to match, e.g. for a user
// account, there might be 2 attrs: their full name and their email.
// * split_char is the separator for this syntax (e.g. ' ').
exports.query_matches_source_attrs = (query, source, match_attrs, split_char) => {
    return _.any(match_attrs, function (attr) {
        const source_str = source[attr].toLowerCase();
        return query_matches_string(query, source_str, split_char);
    });
};

function clean_query(query) {
    query = exports.remove_diacritics(query);
    // When `abc ` with a space at the end is typed in a
    // contenteditable widget such as the composebox PM section, the
    // space at the end was a `no break-space (U+00A0)` instead of
    // `space (U+0020)`, which lead to no matches in those cases.
    query = query.replace(/\u00A0/g, String.fromCharCode(32));

    return query;
}

exports.clean_query_lowercase = function (query) {
    query = query.toLowerCase();
    query = clean_query(query);
    return query;
};

exports.get_emoji_matcher = (query) => {
    // replaces spaces with underscores for emoji matching
    query = query.split(" ").join("_");
    query = exports.clean_query_lowercase(query);

    return function (emoji) {
        return exports.query_matches_source_attrs(query, emoji, ["emoji_name"], "_");
    };
};

