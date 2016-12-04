var timerender = (function () {

var exports = {};

var next_timerender_id = 0;

var set_to_start_of_day = function (time) {
    return time.setMilliseconds(0).setSeconds(0).setMinutes(0).setHours(0);
};

function now() { return new XDate(); }

// Given an XDate object 'time', return a two-element list containing
//   - a string for the current human-formatted version
//   - a boolean for if it will need to be updated when the day changes
exports.render_now = function (time) {
    var start_of_today = set_to_start_of_day(now());
    var start_of_other_day = set_to_start_of_day(time.clone());

    // How many days old is 'time'? 0 = today, 1 = yesterday, 7 = a
    // week ago, -1 = tomorrow, etc.

    // Presumably the result of diffDays will be an integer in this
    // case, but round it to be sure before comparing to integer
    // constants.
    var days_old = Math.round(start_of_other_day.diffDays(start_of_today));

    if (days_old === 0) {
        return ["Today", true];
    } else if (days_old === 1) {
        return ["Yesterday", true];
    } else if (days_old >= 365) {
        // For long running servers, searching backlog can get ambiguous
        // without a year stamp. Only show year if message is over a year old.
        return [time.toString("MMM\xa0dd,\xa0yyyy"), false];
    }
    // For now, if we get a message from tomorrow, we don't bother
    // rewriting the timestamp when it gets to be tomorrow.

    // "\xa0" is U+00A0 NO-BREAK SPACE.
    // Can't use &nbsp; as that represents the literal string "&nbsp;".
    return [time.toString("MMM\xa0dd"), false];
};

// List of the dates that need to be updated when the day changes.
// Each timestamp is represented as a list of length 2:
//   [id of the span element, XDate representing the time]
var update_list = [];

// The time at the beginning of the next day, when the timestamps are updated.
// Represented as an XDate with hour, minute, second, millisecond 0.
var next_update;
$(function () {
    next_update = set_to_start_of_day(now()).addDays(1);
});

// time_above is an optional argument, to support dates that look like:
// --- ▲ Yesterday ▲ ------ ▼ Today ▼ ---
function maybe_add_update_list_entry(needs_update, id, time, time_above) {
    if (needs_update) {
        if (time_above !== undefined) {
            update_list.push([id, time, time_above]);
        } else {
            update_list.push([id, time]);
        }
    }
}

function render_date_span(elem, time_str, time_above_str) {
    elem.text("");
    if (time_above_str !== undefined) {
        return elem.append('<i class="date-direction icon-vector-caret-up"></i>' +
                           time_above_str).append($('<hr class="date-line">')).append('<i class="date-direction icon-vector-caret-down"></i>'
                           + time_str);
    }
    return elem.append(time_str);
}

// Given an XDate object 'time', return a DOM node that initially
// displays the human-formatted date, and is updated automatically as
// necessary (e.g. changing "Today" to "Yesterday" to "Jul 1").
// If two dates are given, it renders them as:
// --- ▲ Yesterday ▲ ------ ▼ Today ▼ ---

// (What's actually spliced into the message template is the contents
// of this DOM node as HTML, so effectively a copy of the node. That's
// okay since to update the time later we look up the node by its id.)
exports.render_date = function (time, time_above) {
    var id = "timerender" + next_timerender_id;
    next_timerender_id += 1;
    var rendered_time = exports.render_now(time);
    var node = $("<span />").attr('id', id);
    if (time_above !== undefined) {
        var rendered_time_above = exports.render_now(time_above);
        node = render_date_span(node, rendered_time[0], rendered_time_above[0]);
    } else {
        node = render_date_span(node, rendered_time[0]);
    }
    maybe_add_update_list_entry(rendered_time[1], id, time, time_above);
    return node;
};

// This isn't expected to be called externally except manually for
// testing purposes.
exports.update_timestamps = function () {
    var time = now();
    if (time >= next_update) {
        var to_process = update_list;
        update_list = [];

        _.each(to_process, function (elem) {
            var id = elem[0];
            var element = document.getElementById(id);
            // The element might not exist any more (because it
            // was in the zfilt table, or because we added
            // messages above it and re-collapsed).
            if (element !== null) {
                var time = elem[1];
                var time_above;
                var rendered_time = exports.render_now(time);
                if (elem.length === 3) {
                    time_above = elem[2];
                    var rendered_time_above = exports.render_now(time_above);
                    render_date_span($(element), rendered_time[0], rendered_time_above[0]);
                } else {
                    render_date_span($(element), rendered_time[0]);
                }
                maybe_add_update_list_entry(rendered_time[1], id, time, time_above);
            }
        });

        next_update = set_to_start_of_day(time.clone().addDays(1));
    }
};

setInterval(exports.update_timestamps, 60 * 1000);

// XDate.toLocaleDateString and XDate.toLocaleTimeString are
// expensive, so we delay running the following code until we need
// the full date and time strings.
exports.set_full_datetime = function timerender_set_full_datetime(message, time_elem) {
    if (message.full_date_str !== undefined) {
        return;
    }

    var time = new XDate(message.timestamp * 1000);
    // Convert to number of hours ahead/behind UTC.
    // The sign of getTimezoneOffset() is reversed wrt
    // the conventional meaning of UTC+n / UTC-n
    var tz_offset = -time.getTimezoneOffset() / 60;

    message.full_date_str = time.toLocaleDateString();
    message.full_time_str = time.toLocaleTimeString() +
        ' (UTC' + ((tz_offset < 0) ? '' : '+') + tz_offset + ')';

    time_elem.attr('title', message.full_date_str + ' ' + message.full_time_str);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = timerender;
}
