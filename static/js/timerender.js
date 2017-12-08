var timerender = (function () {

var exports = {};

var next_timerender_id = 0;

var set_to_start_of_day = function (time) {
    return time.setMilliseconds(0).setSeconds(0).setMinutes(0).setHours(0);
};

// Given an XDate object 'time', returns an object:
// {
//      time_str:        a string for the current human-formatted version
//      formal_time_str: a string for the current formally formatted version
//                          e.g. "Monday, April 15, 2017"
//      needs_update:    a boolean for if it will need to be updated when the
//                       day changes
// }
exports.render_now = function (time, today) {
    var start_of_today = set_to_start_of_day(today || new XDate());
    var start_of_other_day = set_to_start_of_day(time.clone());

    var time_str = '';
    var needs_update = false;
    // render formal time to be used as title attr tooltip
    // "\xa0" is U+00A0 NO-BREAK SPACE.
    // Can't use &nbsp; as that represents the literal string "&nbsp;".
    var formal_time_str = time.toString('dddd,\xa0MMMM\xa0d,\xa0yyyy');

    // How many days old is 'time'? 0 = today, 1 = yesterday, 7 = a
    // week ago, -1 = tomorrow, etc.

    // Presumably the result of diffDays will be an integer in this
    // case, but round it to be sure before comparing to integer
    // constants.
    var days_old = Math.round(start_of_other_day.diffDays(start_of_today));

    var is_older_year =
        (start_of_today.getFullYear() - start_of_other_day.getFullYear()) > 0;

    if (days_old === 0) {
        time_str = i18n.t("Today");
        needs_update = true;
    } else if (days_old === 1) {
        time_str = i18n.t("Yesterday");
        needs_update = true;
    } else if (is_older_year) {
        // For long running servers, searching backlog can get ambiguous
        // without a year stamp. Only show year if message is from an older year
        time_str = time.toString("MMM\xa0dd,\xa0yyyy");
        needs_update = false;
    } else {
        // For now, if we get a message from tomorrow, we don't bother
        // rewriting the timestamp when it gets to be tomorrow.
        time_str = time.toString("MMM\xa0dd");
        needs_update = false;
    }
    return {
        time_str: time_str,
        formal_time_str: formal_time_str,
        needs_update: needs_update,
    };
};

// Current date is passed as an argument for unit testing
exports.last_seen_status_from_date = function (last_active_date, current_date) {
    if (typeof  current_date === 'undefined') {
         current_date = new XDate();
    }

    var minutes = Math.floor(last_active_date.diffMinutes(current_date));
    if (minutes <= 2) {
        return i18n.t("Last seen just now");
    }
    if (minutes < 60) {
        return i18n.t("Last seen __minutes__ minutes ago", {minutes: minutes});
    }

    var hours = Math.floor(minutes / 60);
    if (hours === 1) {
         return i18n.t("Last seen an hour ago");
    }
    if (hours < 24) {
        return i18n.t("Last seen __hours__ hours ago", {hours: hours});
    }

    var days = Math.floor(hours / 24);
    if (days === 1) {
        return [i18n.t("Last seen yesterday")];
    }
    if (days < 365) {
        return i18n.t("Last seen on __last_active__",
                      {last_active: last_active_date.toString("MMM\xa0dd")});
    }

    return i18n.t("Last seen on __last_active_date__",
                  {last_active_date: last_active_date.toString("MMM\xa0dd,\xa0yyyy")});
};

// List of the dates that need to be updated when the day changes.
// Each timestamp is represented as a list of length 2:
//   [id of the span element, XDate representing the time]
var update_list = [];

// The time at the beginning of the next day, when the timestamps are updated.
// Represented as an XDate with hour, minute, second, millisecond 0.
var next_update;
$(function () {
    next_update = set_to_start_of_day(new XDate()).addDays(1);
});

// time_above is an optional argument, to support dates that look like:
// --- ▲ Yesterday ▲ ------ ▼ Today ▼ ---
function maybe_add_update_list_entry(entry) {
    if (entry.needs_update) {
        update_list.push(entry);
    }
}

function render_date_span(elem, rendered_time, rendered_time_above) {
    elem.text("");
    if (rendered_time_above !== undefined) {
        var pieces = [
            '<i class="date-direction icon-vector-caret-up"></i>',
            rendered_time_above.time_str,
            '<hr class="date-line">',
            '<i class="date-direction icon-vector-caret-down"></i>',
            rendered_time.time_str,
        ];
        elem.append(pieces);
        return elem;
    }
    elem.append(rendered_time.time_str);
    return elem.attr('title', rendered_time.formal_time_str);
}

// Given an XDate object 'time', return a DOM node that initially
// displays the human-formatted date, and is updated automatically as
// necessary (e.g. changing "Today" to "Yesterday" to "Jul 1").
// If two dates are given, it renders them as:
// --- ▲ Yesterday ▲ ------ ▼ Today ▼ ---

// (What's actually spliced into the message template is the contents
// of this DOM node as HTML, so effectively a copy of the node. That's
// okay since to update the time later we look up the node by its id.)
exports.render_date = function (time, time_above, today) {
    var className = "timerender" + next_timerender_id;
    next_timerender_id += 1;
    var rendered_time = exports.render_now(time, today);
    var node = $("<span />").attr('class', className);
    if (time_above !== undefined) {
        var rendered_time_above = exports.render_now(time_above, today);
        node = render_date_span(node, rendered_time, rendered_time_above);
    } else {
        node = render_date_span(node, rendered_time);
    }
    maybe_add_update_list_entry({
      needs_update: rendered_time.needs_update,
      className: className,
      time: time,
      time_above: time_above,
    });
    return node;
};

// This isn't expected to be called externally except manually for
// testing purposes.
exports.update_timestamps = function () {
    var now = new XDate();
    if (now >= next_update) {
        var to_process = update_list;
        update_list = [];

        _.each(to_process, function (entry) {
            var className = entry.className;
            var elements = $('.' + className);
            // The element might not exist any more (because it
            // was in the zfilt table, or because we added
            // messages above it and re-collapsed).
            if (elements !== null) {
                _.each(elements, function (element) {
                    var time = entry.time;
                    var time_above = entry.time_above;
                    var rendered_time = exports.render_now(time);
                    if (time_above) {
                        var rendered_time_above = exports.render_now(time_above);
                        render_date_span($(element), rendered_time, rendered_time_above);
                    } else {
                        render_date_span($(element), rendered_time);
                    }
                    maybe_add_update_list_entry({
                        needs_update: rendered_time.needs_update,
                        className: className,
                        time: time,
                        time_above: time_above,
                    });
                });
            }
        });

        next_update = set_to_start_of_day(now.clone().addDays(1));
    }
};

setInterval(exports.update_timestamps, 60 * 1000);

// Transform a Unix timestamp into a ISO 8601 formatted date string.
//   Example: 1978-10-31T13:37:42Z
exports.get_full_time = function (timestamp) {
    return new XDate(timestamp * 1000).toISOString();
};


// this is for rendering absolute time based off the preferences for twenty-four
// hour time in the format of "%mmm %d, %h:%m %p".
exports.absolute_time = (function () {
    var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    var fmt_time = function (date, H_24) {
        var payload = {
            hours: date.getHours(),
            minutes: date.getMinutes(),
        };

        if (payload.hours > 12 && !H_24) {
            payload.hours -= 12;
            payload.is_pm = true;
        }

        var str = ("0" + payload.hours).slice(-2) + ":" + ("0" + payload.minutes).slice(-2);

        if (!H_24) {
            str += payload.is_pm ? " PM" : " AM";
        }

        return str;
    };

    return function (timestamp, today) {
        if (typeof today === 'undefined') {
             today = new Date();
        }
        var date = new Date(timestamp);
        var is_older_year = (today.getFullYear() - date.getFullYear()) > 0;
        var H_24 = page_params.twenty_four_hour_time;
        var str = MONTHS[date.getMonth()] + " " + date.getDate();
        // include year if message date is from a previous year
        if (is_older_year) {
            str += ", " + date.getFullYear();
        }
        str += " " + fmt_time(date, H_24);
        return str;
    };
}());

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
