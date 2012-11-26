var typeahead_helper = (function () {

var exports = {};

var autocomplete_needs_update = false;
exports.autocomplete_needs_update = function (needs_update) {
    if (needs_update === undefined) {
        return autocomplete_needs_update;
    } else {
        autocomplete_needs_update = needs_update;
    }
};

exports.update_autocomplete = function () {
    stream_list.sort();
    search.update_typeahead();
    autocomplete_needs_update = false;
};


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
    $.each(pieces, function(idx, piece) {
        if (piece.match(regex)) {
            result += "<strong>" + Handlebars.Utils.escapeExpression(piece) + "</strong>";
        } else {
            result += Handlebars.Utils.escapeExpression(piece);
        }
    });
    return result;
};

exports.private_message_typeahead_list = [];
exports.private_message_mapped = {};

function render_pm_object(person) {
    return person.full_name + " <" + person.email + ">";
}

function add_to_known_recipients(recipient_data, count_towards_autocomplete_preference) {
    var name_string = render_pm_object(recipient_data);
    if (typeahead_helper.private_message_mapped[name_string] === undefined) {
        typeahead_helper.private_message_mapped[name_string] = recipient_data;
        typeahead_helper.private_message_mapped[name_string].count = 0;
        typeahead_helper.private_message_typeahead_list.push(name_string);
    }
    if (count_towards_autocomplete_preference) {
        typeahead_helper.private_message_mapped[name_string].count += 1;
    }
}

exports.known_to_typeahead = function (recipient_data) {
    return typeahead_helper.private_message_mapped[render_pm_object(recipient_data)] !== undefined;
};

exports.update_all_recipients = function (recipients) {
    $.each(recipients, function (idx, recipient_data) {
        add_to_known_recipients(recipient_data, false);
    });
};

exports.update_your_recipients = function (recipients) {
    $.each(recipients, function (idx, recipient_data) {
        if (recipient_data.email !== email) {
            add_to_known_recipients(recipient_data, true);
        }
    });
};

exports.sorter = function (query, objs, get_item) {
    // Based on Bootstrap typeahead's default sorter, but taking into
    // account case sensitivity on "begins with"
    var beginswithCaseSensitive = [];
    var beginswithCaseInsensitive = [];
    var caseSensitive = [];
    var caseInsensitive = [];

    var obj = objs.shift();
    while (obj) {
        var item = get_item(obj);
        if (item.indexOf(query) === 0)
            beginswithCaseSensitive.push(obj);
        else if (item.toLowerCase().indexOf(query.toLowerCase()) !== -1)
            beginswithCaseInsensitive.push(obj);
        else if (item.indexOf(query) !== -1)
            caseSensitive.push(obj);
        else
            caseInsensitive.push(obj);
        obj = objs.shift();
    }
    return beginswithCaseSensitive.concat(beginswithCaseInsensitive,
                                          caseSensitive,
                                          caseInsensitive);
};

function identity(item) {
    return item;
}

exports.sort_streams = function (items) {
    return typeahead_helper.sorter(this.query, items, identity);
};

exports.sort_subjects = function (items) {
    return typeahead_helper.sorter(this.query, items, identity);
};

return exports;

}());
