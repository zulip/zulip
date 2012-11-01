var composebox_typeahead = (function () {

var exports = {};

var autocomplete_needs_update = false;

exports.autocomplete_needs_update = function (needs_update) {
    if (needs_update === undefined) {
        return autocomplete_needs_update;
    } else {
        autocomplete_needs_update = needs_update;
    }
};

var huddle_typeahead_list = [];

exports.update_autocomplete = function () {
    stream_list.sort();
    people_list.sort(function (x, y) {
        if (x.email === y.email) return 0;
        if (x.email < y.email) return -1;
        return 1;
    });

    huddle_typeahead_list = $.map(people_list, function (person) {
        return person.full_name + " <" + person.email + ">";
    });

    autocomplete_needs_update = false;
};

//************************************
// AN IMPORTANT NOTE ABOUT TYPEAHEADS
//************************************
// They do not do any HTML escaping, at all.
// And your input to them is rendered as though it were HTML by
// the default highlighter.
//
// So if you are not using trusted input, you MUST use the
// escaping_highlighter.
function escaping_highlighter(item) {
    // (BASED ON Bootstrap's default highlighter, but with escaping added.)
    var query = this.query.replace(/[\-\[\]{}()*+?.,\\\^$|#\s]/g, '\\$&');
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
}

exports.initialize = function () {
    // limit number of items so the list doesn't fall off the screen
    $( "#stream" ).typeahead({
        source: function (query, process) {
            return stream_list;
        },
        items: 3,
        highlighter: escaping_highlighter
    });
    $( "#subject" ).typeahead({
        source: function (query, process) {
            var stream_name = $("#stream").val();
            if (subject_dict.hasOwnProperty(stream_name)) {
                return subject_dict[stream_name];
            }
            return [];
        },
        items: 2,
        highlighter: escaping_highlighter
    });
    $( "#huddle_recipient" ).typeahead({
        source: function (query, process) {
            return huddle_typeahead_list;
        },
        items: 4,
        highlighter: escaping_highlighter,
        matcher: function (item) {
            // Assumes email addresses don't have commas or semicolons in them
            var recipients = this.query.split(/[,;] */);
            var current_recipient = recipients[recipients.length-1];
            // Case-insensitive (from Bootstrap's default matcher).
            return (item.toLowerCase().indexOf(current_recipient.toLowerCase()) !== -1);
        },
        updater: function (item) {
            var previous_recipients = this.query.split(/[,;] */);
            previous_recipients.pop();
            previous_recipients = previous_recipients.join(", ");
            if (previous_recipients.length !== 0) {
                previous_recipients += ", ";
            }
            // Extracting the email portion via regex is icky, but the Bootstrap
            // typeahead widget doesn't seem to be flexible enough to pass
            // objects around
            var email_re = /<[^<]*>$/;
            var email = email_re.exec(item)[0];
            return previous_recipients + email.substring(1, email.length - 1) + ", ";
        }
    });

    $( "#huddle_recipient" ).blur(function (event) {
        var val = $(this).val();
        $(this).val(val.replace(/[,;] *$/, ''));
    });

    composebox_typeahead.update_autocomplete();
};

return exports;

}());
