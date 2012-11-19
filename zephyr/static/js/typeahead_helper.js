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
    people_list.sort(function (x, y) {
        if (x.email === y.email) return 0;
        if (x.email < y.email) return -1;
        return 1;
    });

    composebox_typeahead.update_typeahead();
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

return exports;

}());
