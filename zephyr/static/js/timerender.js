var timerender = (function () {

var exports = {};

// If this is 5, then times from up to 5 days before the current
// day will be formatted as weekday names:
//
//                     1/10 1/11 1/12
// Sun  Mon  Tue  Wed  Thu  1/18 1/19
//                     ^ today
var MAX_AGE_FOR_WEEKDAY = 5;

var next_timerender_id = 0;

var set_to_start_of_day = function (time) {
    return time.setMilliseconds(0).setSeconds(0).setMinutes(0).setHours(0);
};

function now() { return (new XDate()); }

// Given an XDate object 'time', return a two-element list containing
//   - a string for the current human-formatted version
//   - a string like "2013-01-20" representing the day the format
//     needs to change, or undefined if it will never need to change.
function render_now(time) {
    var start_of_today = set_to_start_of_day(now());
    var start_of_other_day = set_to_start_of_day(time.clone());

    // How many days old is 'time'? 0 = today, 1 = yesterday, 7 = a
    // week ago, -1 = tomorrow, etc.

    // Presumably the result of diffDays will be an integer in this
    // case, but round it to be sure before comparing to integer
    // constants.
    var days_old = Math.round(start_of_other_day.diffDays(start_of_today));

    if (days_old >= 0 && days_old <= MAX_AGE_FOR_WEEKDAY)
        // "\xa0" is U+00A0 NO-BREAK SPACE.
        // Can't use &nbsp; as that represents the literal string "&nbsp;".
        return [time.toString("ddd") + "\xa0" + time.toString("HH:mm"),
                start_of_other_day.addDays(MAX_AGE_FOR_WEEKDAY+1)
                .toString("yyyy-MM-dd")];
    else {
        // For now, if we get a message from tomorrow, we don't bother
        // rewriting the timestamp when it gets to be tomorrow.
        return [time.toString("MMM dd") + "\xa0\xa0" + time.toString("HH:mm"),
                undefined];
    }
}

// This table associates to each day (represented as a yyyy-MM-dd
// string) a list of timestamps that need to be updated on that day.
// Each timestamp is represented as a list of length 2:
//   [id of the span element, XDate representing the time]

// This is an efficient data structure because we only need to update
// timestamps at the start of each day. If timestamp update times were
// arbitrary, a priority queue would be more sensible.
var update_table = {};

// The day that elements are currently up-to-date with respect to.
// Represented as an XDate with hour, minute, second, millisecond 0.
var last_updated = set_to_start_of_day(now());

function maybe_add_update_table_entry(update_date, id, time) {
    if (update_date === undefined)
        return;
    if (update_table[update_date] === undefined)
        update_table[update_date] = [];
    update_table[update_date].push([id, time]);
}

// Given an XDate object 'time', return a DOM node that initially
// displays the human-formatted time, and is updated automatically as
// necessary (e.g. changing "Mon 11:21" to "Jan 14 11:21" after a week
// or so).

// (What's actually spliced into the message template is the contents
// of this DOM node as HTML, so effectively a copy of the node. That's
// okay since to update the time later we look up the node by its id.)
exports.render_time = function (time) {
    var id = "timerender" + next_timerender_id;
    next_timerender_id++;
    var rendered_now = render_now(time);
    var node = $("<span />").attr('id', id).text(rendered_now[0]);
    maybe_add_update_table_entry(rendered_now[1], id, time);
    return node;
};

// This isn't expected to be called externally except manually for
// testing purposes.
exports.update_timestamps = function () {
    var start_of_today = set_to_start_of_day(now());
    var new_date;
    // This loop won't do anything unless the day changed since the
    // last time it ran.
    for (new_date = last_updated.clone().addDays(1);
         new_date <= start_of_today;
         new_date.addDays(1)) {
        var update_date = new_date.toString("yyyy-MM-dd");
        if (update_table[update_date] !== undefined)
        {
            var to_process = update_table[update_date];
            var i;
            update_table[update_date] = [];
            $.each(to_process, function (idx, elem) {
                var id = elem[0];
                var element = document.getElementById(id);
                // The element might not exist any more (because it
                // was in the zfilt table, or because we added
                // messages above it and re-collapsed).
                if (element !== null) {
                    var time = elem[1];
                    var new_rendered = render_now(time);
                    $(document.getElementById(id)).text(new_rendered[0]);

                    maybe_add_update_table_entry(new_rendered[1], id, time);
                }
            });
        }
    }
    last_updated = start_of_today;
};

setInterval(exports.update_timestamps, 60 * 1000);

return exports;
}());
