var composebox_typeahead = (function () {

//************************************
// AN IMPORTANT NOTE ABOUT TYPEAHEADS
//************************************
// They do not do any HTML escaping, at all.
// And your input to them is rendered as though it were HTML by
// the default highlighter.
//
// So if you are not using trusted input, you MUST use the a
// highlighter that escapes (i.e. one that calls
// typeahead_helper.highlight_with_escaping).

var exports = {};

var private_message_typeahead_list = [];
var private_message_mapped = {};

function render_pm_object(person) {
    return person.full_name + " <" + person.email + ">";
}

exports.update_typeahead = function() {
    private_message_mapped = {};
    private_message_typeahead_list = [];
    $.each(people_list, function (i, obj) {
        var label = render_pm_object(obj);
        private_message_mapped[label] = obj;
        private_message_typeahead_list.push(label);
    });
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

function composebox_typeahead_highlighter(item) {
    var query = this.query;
    if ($(this.$element).attr('id') === 'private_message_recipient') {
        // There could be multiple recipients in a private message,
        // we want to decide what to highlight based only on the most
        // recent one we're entering.
        query = get_last_recipient_in_pm(this.query);
    }
    return typeahead_helper.highlight_with_escaping(query, item);
}

// nextFocus is set on a keydown event to indicate where we should focus on keyup.
// We can't focus at the time of keydown because we need to wait for typeahead.
// And we can't compute where to focus at the time of keyup because only the keydown
// has reliable information about whether it was a tab or a shift+tab.
var nextFocus = false;

function handle_keydown(e) {
    var code = e.keyCode || e.which;

    if (code === 13 || (code === 9 && !e.shiftKey)) { // Enter key or tab key
        if (e.target.id === "stream" || e.target.id === "subject" || e.target.id === "private_message_recipient") {
            // For enter, prevent the form from submitting
            // For tab, prevent the focus from changing again
            e.preventDefault();
        }

        if (e.target.id === "stream") {
            nextFocus = "subject";
        } else if (e.target.id === "subject") {
            if (code === 13) e.preventDefault();
            nextFocus = "new_message_content";
        } else if (e.target.id === "private_message_recipient") {
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
    select_on_focus("private_message_recipient");

    // These handlers are at the "form" level so that they are called after typeahead
    $("form#send_message_form").keydown(function(e) {
        handle_keydown(e);
    });
    $("form#send_message_form").keyup(function(e) {
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
            var obj = private_message_mapped[item];
            var previous_recipients = get_cleaned_pm_recipients(this.query);
            previous_recipients.pop();
            previous_recipients = previous_recipients.join(", ");
            if (previous_recipients.length !== 0) {
                previous_recipients += ", ";
            }
            return previous_recipients + obj.email + ", ";
        },
        stopAdvance: true // Do not advance to the next field on a tab or enter
    });

    $( "#private_message_recipient" ).blur(function (event) {
        var val = $(this).val();
        var recipients = get_cleaned_pm_recipients(val);
        $(this).val(recipients.join(", "));
    });

    typeahead_helper.update_autocomplete();
};

return exports;

}());
