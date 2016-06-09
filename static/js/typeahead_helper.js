var typeahead_helper = (function () {

var exports = {};

// Loosely based on Bootstrap's default highlighter, but with escaping added.
exports.highlight_with_escaping = function (query, item) {
    // query: The text currently in the searchbox
    // item: The string we are trying to appropriately highlight
    query = query.replace(/[\-\[\]{}()*+?.,\\\^$|#\s]/g, '\\$&');
    var regex = new RegExp('(' + query + ')', 'ig');
    // The result of the split will include the query term, because our regex
    // has parens in it.
    // (as per https://developer.mozilla.org/en-US/docs/JavaScript/Reference/Global_Objects/String/split)
    // However, "not all browsers support this capability", so this is a place to look
    // if we have an issue here in, e.g. IE.
    var pieces = item.split(regex);
    // We need to assemble this manually (as opposed to doing 'join') because we need to
    // (1) escape all the pieces and (2) the regex is case-insensitive, and we need
    // to know the case of the content we're replacing (you can't just use a bolded
    // version of 'query')
    var result = "";
    _.each(pieces, function (piece) {
        if (piece.match(regex)) {
            result += "<strong>" + Handlebars.Utils.escapeExpression(piece) + "</strong>";
        } else {
            result += Handlebars.Utils.escapeExpression(piece);
        }
    });
    return result;
};

exports.highlight_with_escaping_and_regex = function (regex, item) {
    var pieces = item.split(regex);
    var result = "";
    _.each(pieces, function (piece) {
        if (piece.match(regex)) {
            result += "<strong>" + Handlebars.Utils.escapeExpression(piece) + "</strong>";
        } else {
            result += Handlebars.Utils.escapeExpression(piece);
        }
    });
    return result;
};

exports.highlight_query_in_phrase = function (query, phrase) {
    var i;
    query = query.toLowerCase();
    query = query.replace(/[\-\[\]{}()*+?.,\\\^$|#\s]/g, '\\$&');
    var regex = new RegExp('(^' + query + ')', 'ig');

    var result = "";
    var parts = phrase.split(' ');
    for (i = 0; i < parts.length; i++) {
        if (i > 0) {
            result += " ";
        }
        result += exports.highlight_with_escaping_and_regex(regex, parts[i]);
    }
    return result;
};

exports.render_person = function (person) {
    if (person.special_item_text) {
        return person.special_item_text;
    }
    return person.full_name + " <" + person.email + ">";
};

function prefix_sort(query, objs, get_item) {
    // Based on Bootstrap typeahead's default sorter, but taking into
    // account case sensitivity on "begins with"
    var beginswithCaseSensitive = [];
    var beginswithCaseInsensitive = [];
    var noMatch = [];

    var obj = objs.shift();
    while (obj) {
        var item;
        if (get_item) {
            item = get_item(obj);
        }
        else {
            item = obj;
        }
        if (item.indexOf(query) === 0) {
            beginswithCaseSensitive.push(obj);
        } else if (item.toLowerCase().indexOf(query.toLowerCase()) === 0) {
            beginswithCaseInsensitive.push(obj);
        } else {
            noMatch.push(obj);
        }
        obj = objs.shift();
    }
    return { matches: beginswithCaseSensitive.concat(beginswithCaseInsensitive),
             rest:    noMatch };

}

exports.sorter = function (query, objs, get_item) {
   var results = prefix_sort(query, objs, get_item);
   return results.matches.concat(results.rest);
};

exports.compare_by_pms = function (user_a, user_b) {
    if (user_a.pm_recipient_count > user_b.pm_recipient_count) {
        return -1;
    } else if (user_a.pm_recipient_count < user_b.pm_recipient_count) {
        return 1;
    }

    if (!user_a.is_bot && user_b.is_bot) {
        return -1;
    } else if (user_a.is_bot && !user_b.is_bot) {
        return 1;
    }

    // We use alpha sort as a tiebreaker, which might be helpful for
    // new users.
    if (user_a.full_name < user_b.full_name) {
        return -1;
    } else if (user_a === user_b) {
        return 0;
    } else {
        return 1;
    }
};

exports.sort_by_pms = function (objs) {
    objs.sort(exports.compare_by_pms);
    return objs;
};

function identity(item) {
    return item;
}

exports.sort_recipients = function (matches, query) {
    var name_results =  prefix_sort(query, matches, function (x) { return x.full_name; });
    var email_results = prefix_sort(query, name_results.rest, function (x) { return x.email; });
    var matches_sorted_by_pms = exports.sort_by_pms(name_results.matches.concat(email_results.matches));
    var rest_sorted_by_pms = exports.sort_by_pms(email_results.rest);
    return matches_sorted_by_pms.concat(rest_sorted_by_pms);
};

exports.sort_emojis = function (matches, query) {
    // TODO: sort by category in v2
    var results = prefix_sort(query, matches, function (x) { return x.emoji_name; });
    return results.matches.concat(results.rest);
};

exports.sort_recipientbox_typeahead = function (matches) {
    // input_text may be one or more pm recipients
    var cleaned = composebox_typeahead.get_cleaned_pm_recipients(this.query);
    var query = cleaned[cleaned.length - 1];
    return exports.sort_recipients(matches, query);};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = typeahead_helper;
}
