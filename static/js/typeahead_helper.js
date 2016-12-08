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
    for (i = 0; i < parts.length; i += 1) {
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
        } else {
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
exports.compare_by_pms = function (user_a, user_b, selected_recipient,
                                   current_stream_persons,
                                   current_subject_persons) {
    var count_a = people.get_recipient_count(user_a);
    var count_b = people.get_recipient_count(user_b);
    if (user_a.full_name === selected_recipient) {
        return -1;
    } else if (user_b.full_name === selected_recipient) {
        return 1;
    }
     if (current_subject_persons.indexOf(user_a.full_name) >= 0) {
         return -1;
     } else if (current_subject_persons.indexOf(user_b.full_name) >= 0) {
         return 1;
     }
    if (current_stream_persons.indexOf(user_a.full_name) >= 0) {
        return -1;
    } else if (current_stream_persons.indexOf(user_b.full_name) >= 0) {
        return 1;
    }
    if (count_a > count_b) {
        return -1;
    } else if (count_a < count_b) {
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
    }
    return 1;
};

exports.organize = function (user_a, user_b) {
    var current_subject = $('#subject.recipient_box').val();
    var current_stream = $('#stream.recipient_box').val();
    // Filter functions for subject and stream passes the ones that the user
    // itself didn't send and the ones that belong to current subject and stream
    function pSubject(message) {
        if (message.sent_by_me === false && message.subject === current_subject) {
            return true;
        }
    }
    function pStream(message) {
        if (message.sent_by_me === false && message.stream === current_stream) {
           return true;
        }
    }
    var current_subject_persons_info = message_list.all._items.filter(pSubject);
    var current_stream_persons_info = message_list.all._items.filter(pStream);
    var current_subject_persons = [];
    var current_stream_persons = [];
    var names_in_current_subject = [];
    var names_in_current_stream = [];
    var selected_recipient = "";
    var i = 0;
    for (i = 0; i < current_subject_persons_info.length; i += 1) {
         names_in_current_subject.push(current_subject_persons_info[i].sender_full_name);
    }
    for (i = 0; i < current_stream_persons_info.length; i += 1) {
        names_in_current_stream.push(current_stream_persons_info[i].sender_full_name);
    }
    // Deleting repeated objects in these arrays
    current_subject_persons = names_in_current_subject.filter(function (elem, pos) {
        return names_in_current_subject.indexOf(elem) === pos;
    });
    if (current_subject_persons.length > 10) {
        current_subject_persons.splice(0, current_subject_persons.length - 10);
    }
    current_stream_persons = names_in_current_stream.filter(function (elem, pos) {
        return names_in_current_stream.indexOf(elem) === pos;
    });
    if (current_stream_persons.length > 10) {
        current_stream_persons.splice(0, current_stream_persons.length - 10);
    }
    for (i = message_list.all._items.length - 1; i > 0; i -= 1) {
        if ($("#zfilt" + String(message_list.all._items[i].id)).hasClass('selected_message') === true ||$("#zhome" + String(message_list.all._items[i].id)).hasClass('selected_message') === true ) {
            selected_recipient = message_list.all._items[i].sender_full_name;
        }
    }
    return exports.compare_by_pms(user_a, user_b, selected_recipient,
                                  current_stream_persons, current_subject_persons);
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
    var matches_sorted_by_pms =
        exports.sort_by_pms(name_results.matches.concat(email_results.matches));
    var rest_sorted_by_pms = exports.sort_by_pms(email_results.rest);
    return matches_sorted_by_pms.concat(rest_sorted_by_pms);
};

exports.sort_emojis = function (matches, query) {
    // TODO: sort by category in v2
    var results = prefix_sort(query, matches, function (x) { return x.emoji_name; });
    return results.matches.concat(results.rest);
};

exports.sort_streams = function (matches, query) {
    var results = prefix_sort(query, matches, function (x) { return x; });
    return results.matches.concat(results.rest);
};

exports.sort_recipientbox_typeahead = function (matches) {
    // input_text may be one or more pm recipients
    var cleaned = composebox_typeahead.get_cleaned_pm_recipients(this.query);
    var query = cleaned[cleaned.length - 1];
    return exports.sort_recipients(matches, query);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = typeahead_helper;
}
