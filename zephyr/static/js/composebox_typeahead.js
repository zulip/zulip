var composebox_typeahead = (function () {

//************************************
// AN IMPORTANT NOTE ABOUT TYPEAHEADS
//************************************
// They do not do any HTML escaping, at all.
// And your input to them is rendered as though it were HTML by
// the default highlighter.
//
// So if you are not using trusted input, you MUST use the a
// highlighter that escapes, such as composebox_typeahead_highlighter
// below.

var exports = {};

var autocomplete_needs_update = false;

exports.autocomplete_needs_update = function (needs_update) {
    if (needs_update === undefined) {
        return autocomplete_needs_update;
    } else {
        autocomplete_needs_update = needs_update;
    }
};

var private_message_typeahead_list = [];

exports.update_autocomplete = function () {
    stream_list.sort();
    people_list.sort(function (x, y) {
        if (x.email === y.email) return 0;
        if (x.email < y.email) return -1;
        return 1;
    });

    private_message_typeahead_list = $.map(people_list, function (person) {
        return person.full_name + " <" + person.email + ">";
    });

    autocomplete_needs_update = false;
};

function get_pm_recipients(query_string) {
    // Assumes email addresses don't have commas or semicolons in them
    return query_string.split(/\s*[,;]\s*/);
}

// Returns an array of private message recipients, removing empty elements.
// For example, "a,,b, " => ["a", "b"]
function get_cleaned_pm_recipients(query_string) {
    var recipients = get_pm_recipients(query_string);
    recipients = $.grep(recipients, function (elem, idx) {
        return elem.match(/\S/);
    });
    return recipients;
}

function get_last_recipient_in_pm(query_string) {
    var recipients = get_pm_recipients(query_string);
    return recipients[recipients.length-1];
}

// Loosely based on Bootstrap's default highlighter, but with escaping added.
function composebox_typeahead_highlighter(item) {
    var query = this.query;
    if ($(this.$element).attr('id') === 'private_message_recipient') {
        // There could be multiple recipients in a private message,
        // we want to decide what to highlight based only on the most
        // recent one we're entering.
        query = get_last_recipient_in_pm(this.query);
    }
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
}

// nextFocus is set on a keydown event to indicate where we should focus on keyup.
// We can't focus at the time of keydown because we need to wait for typeahead.
// And we can't compute where to focus at the time of keyup because only the keydown
// has reliable information about whether it was a tab or a shift+tab.
var nextFocus = false;

function handle_keydown(e) {
    var code = e.keyCode || e.which;

    if (code === 13 || (code === 9 && !e.shiftKey)) { // Enter key or tab key
        if (e.target.id === "stream" || e.target.id === "subject" || e.target.id === "huddle_recipient") {
            // For enter, prevent the form from submitting
            // For tab, prevent the focus from changing again
            e.preventDefault();
        }

        if (e.target.id === "stream") {
            nextFocus = "subject";
        } else if (e.target.id === "subject") {
            if (code === 13) e.preventDefault();
            nextFocus = "new_message_content";
        } else if (e.target.id === "huddle_recipient") {
            nextFocus = "new_message_content";
        } else {
            nextFocus = false;
        }

        return false;
    }
}

function handle_keyup(e) {
    var code = e.keyCode || e.which;
    if (code === 13 || (code === 9 && !e.shiftKey)) { // Enter key or tab key
        if (nextFocus) {
            focus_on(nextFocus);
            nextFocus = false;
        }
    }
}

// http://stackoverflow.com/questions/3380458/looking-for-a-better-workaround-to-chrome-select-on-focus-bug
function select_on_focus(field_id) {
    $("#" + field_id).focus(function(e) {
        $("#" + field_id).select().mouseup(function (e) {
            e.preventDefault();
            $(this).unbind("mouseup");
        });
    });
}

exports.initialize = function () {
    select_on_focus("stream");
    select_on_focus("subject");
    select_on_focus("huddle_recipient");

    // These handlers are at the "form" level so that they are called after typeahead
    $("form").keydown(function(e) {
        handle_keydown(e);
    });
    $("form").keyup(function(e) {
        handle_keyup(e);
    });

    // limit number of items so the list doesn't fall off the screen
    $( "#stream" ).typeahead({
        source: function (query, process) {
            return stream_list;
        },
        items: 3,
        highlighter: composebox_typeahead_highlighter
    });

    $( "#subject" ).typeahead({
        source: function (query, process) {
            var stream_name = $("#stream").val();
            if (subject_dict.hasOwnProperty(stream_name)) {
                return subject_dict[stream_name];
            }
            return [];
        },
        items: 3,
        highlighter: composebox_typeahead_highlighter
    });
    $( "#private_message_recipient" ).typeahead({
        source: function (query, process) {
            return private_message_typeahead_list;
        },
        items: 4,
        highlighter: composebox_typeahead_highlighter,
        matcher: function (item) {
            var current_recipient = get_last_recipient_in_pm(this.query);
            // If the name is only whitespace (does not contain any non-whitespace),
            // we're between typing names; don't autocomplete anything for us.
            if (! current_recipient.match(/\S/)) {
                return false;
            }
            // Case-insensitive (from Bootstrap's default matcher).
            return (item.toLowerCase().indexOf(current_recipient.toLowerCase()) !== -1);
        },
        updater: function (item) {
            var previous_recipients = get_cleaned_pm_recipients(this.query);
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
        },
        stopAdvance: true // Do not advance to the next field on a tab or enter
    });

    $( "#private_message_recipient" ).blur(function (event) {
        var val = $(this).val();
        var recipients = get_cleaned_pm_recipients(val);
        $(this).val(recipients.join(", "));
    });

    composebox_typeahead.update_autocomplete();
};

return exports;

}());
