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

exports.initialize = function () {
    // limit number of items so the list doesn't fall off the screen
    $( "#stream" ).typeahead({
        source: function (query, process) {
            return stream_list;
        },
        items: 3
    });
    $( "#subject" ).typeahead({
        source: function (query, process) {
            var stream_name = $("#stream").val();
            if (subject_dict.hasOwnProperty(stream_name)) {
                return subject_dict[stream_name];
            }
            return [];
        },
        items: 2
    });
    $( "#huddle_recipient" ).typeahead({
        source: function (query, process) {
            return huddle_typeahead_list;
        },
        items: 4,
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
