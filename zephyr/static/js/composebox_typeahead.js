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

function get_pm_recipients(query_string) {
    // Assumes email addresses don't have commas or semicolons in them
    return query_string.split(/\s*[,;]\s*/);
}

// Returns an array of private message recipients, removing empty elements.
// For example, "a,,b, " => ["a", "b"]
exports.get_cleaned_pm_recipients = function (query_string) {
    var recipients = get_pm_recipients(query_string);
    recipients = $.grep(recipients, function (elem, idx) {
        return elem.match(/\S/);
    });
    return recipients;
};

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

        // In the new_message_content box, preventDefault() for tab but not for enter
        if (e.target.id === "new_message_content" && code !== 13) {
            e.preventDefault();
        }

        if (e.target.id === "stream") {
            nextFocus = "subject";
        } else if (e.target.id === "subject") {
            if (code === 13) e.preventDefault();
            nextFocus = "new_message_content";
        } else if (e.target.id === "private_message_recipient") {
            nextFocus = "new_message_content";
        } else if (e.target.id === "new_message_content") {
            if (code === 13) {
                nextFocus = false;
            } else {
                nextFocus = "compose-send-button";
            }
        } else {
            nextFocus = false;
        }

        // If no typeaheads are shown...
        if (!($("#subject").data().typeahead.shown ||
              $("#stream").data().typeahead.shown ||
              $("#private_message_recipient").data().typeahead.shown ||
              $("#new_message_content").data().typeahead.shown)) {

            // If no typeaheads are shown and the user is tabbing from the message content box,
            // then there's no need to wait and we can change the focus right away.
            // Without this code to change the focus right away, if the user presses enter
            // before they fully release the tab key, the tab will be lost.  Note that we don't
            // want to change focus right away in the private_message_recipient box since it
            // takes the typeaheads a little time to open after the user finishes typing, which
            // can lead to the focus moving without the autocomplete having a chance to happen.
            if ((page_params.domain === "humbughq.com" && nextFocus === "compose-send-button") ||
                (page_params.domain !== "humbughq.com" && nextFocus)) {
                ui.focus_on(nextFocus);
                nextFocus = false;
            }

            // If no typeaheads are shown and the user has configured enter to send,
            // then make enter send instead of inserting a line break.
            // (Unless shift is being held down, which we *do* want to insert a linebreak)
            if (e.target.id === "new_message_content"
                && code === 13 && !e.shiftKey
                && page_params.enter_sends) {
                e.preventDefault();
                if ($("#compose-send-button").attr('disabled') !== "disabled") {
                    $("#compose-send-button").attr('disabled', 'disabled');
                    compose.finish();
                }
            }
        }

        return false;
    }
}

function handle_keyup(e) {
    var code = e.keyCode || e.which;
    if (code === 13 || (code === 9 && !e.shiftKey)) { // Enter key or tab key
        if (nextFocus) {
            ui.focus_on(nextFocus);
            nextFocus = false;
        }
    }
}

// http://stackoverflow.com/questions/3380458/looking-for-a-better-workaround-to-chrome-select-on-focus-bug
function select_on_focus(field_id) {
    $("#" + field_id).focus(function(e) {
        $("#" + field_id).select().one('mouseup', function (e) {
            e.preventDefault();
        });
    });
}

exports.split_at_cursor = function(query) {
    var cursor = $('#new_message_content').caret().start;
    return [query.slice(0, cursor), query.slice(cursor)];
};

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

    $("#enter_sends").click(function () {
        var send_button = $("#compose-send-button");
        page_params.enter_sends = $("#enter_sends").is(":checked");
        if (page_params.enter_sends) {
            send_button.fadeOut();
        } else {
            send_button.fadeIn();
        }
        return $.ajax({
            dataType: 'json',
            url: '/json/change_enter_sends',
            type: 'POST',
            data: {'enter_sends': page_params.enter_sends}
        });
    });
    $("#enter_sends").prop('checked', page_params.enter_sends);
    if (page_params.enter_sends) $("#compose-send-button").hide();

    // limit number of items so the list doesn't fall off the screen
    $( "#stream" ).typeahead({
        source: function (query, process) {
            return subs.subscribed_streams();
        },
        items: 3,
        highlighter: function (item) {
            var query = this.query;
            return typeahead_helper.highlight_query_in_phrase(query, item);
        },
        matcher: function (item) {
            // The matcher for "stream" is strictly prefix-based,
            // because we want to avoid mixing up streams.
            var q = this.query.trim().toLowerCase();
            return (item.toLowerCase().indexOf(q) === 0);
        }
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
        highlighter: composebox_typeahead_highlighter,
        sorter: typeahead_helper.sort_subjects
    });

    $( "#private_message_recipient" ).typeahead({
        source: typeahead_helper.private_message_typeahead_list,
        items: 2,
        highlighter: composebox_typeahead_highlighter,
        matcher: function (item) {
            var current_recipient = get_last_recipient_in_pm(this.query);
            // If the name is only whitespace (does not contain any non-whitespace),
            // we're between typing names; don't autocomplete anything for us.
            if (! current_recipient.match(/\S/)) {
                return false;
            }

            // Case-insensitive.
            return (item.toLowerCase().indexOf(current_recipient.toLowerCase()) !== -1);
        },
        sorter: typeahead_helper.sort_recipientbox_typeahead,
        updater: function (item) {
            var previous_recipients = exports.get_cleaned_pm_recipients(this.query);
            previous_recipients.pop();
            previous_recipients = previous_recipients.join(", ");
            if (previous_recipients.length !== 0) {
                previous_recipients += ", ";
            }
            return previous_recipients + typeahead_helper.private_message_mapped[item].email + ", ";
        },
        stopAdvance: true // Do not advance to the next field on a tab or enter
    });

    $( "#new_message_content" ).typeahead({
        source: typeahead_helper.private_message_typeahead_list,
        items: 2,
        highlighter: composebox_typeahead_highlighter,
        matcher: function (item) {
            var query = exports.split_at_cursor(this.query)[0];

            var strings = query.split(/[\s*(){}\[\]]/);
            if (strings.length < 1) {
                return false;
            }
            var current_recipient = strings[strings.length-1];
            if (current_recipient.length < 2 || current_recipient.charAt(0) !== "@") {
                return false;
            }
            current_recipient = current_recipient.substring(1);

            // Case-insensitive.
            return (item.toLowerCase().indexOf(current_recipient.toLowerCase()) !== -1);
        },
        sorter: typeahead_helper.sort_textbox_typeahead,
        updater: function (item) {
            var pieces = exports.split_at_cursor(this.query);
            var beginning = pieces[0];
            var rest = pieces[1];

            beginning = beginning.replace(/@\S+$/, "") + "@**" + typeahead_helper.private_message_mapped[item].full_name + "**";
            // Keep the cursor after the newly inserted name, as Bootstrap will call textbox.change() to overwrite the text
            // in the textbox.
            setTimeout(function () {
                $('#new_message_content').caret(beginning.length, beginning.length);
            }, 0);
            return beginning + rest;
        },
        stopAdvance: true // Do not advance to the next field on a tab or enter
    });

    $( "#private_message_recipient" ).blur(function (event) {
        var val = $(this).val();
        var recipients = exports.get_cleaned_pm_recipients(val);
        $(this).val(recipients.join(", "));
    });

    typeahead_helper.update_autocomplete();
};

return exports;

}());
