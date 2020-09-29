"use strict";

const {format, parseISO, isValid} = require("date-fns");
const XDate = require("xdate");

let next_timerender_id = 0;

const set_to_start_of_day = function (time) {
    return time.setMilliseconds(0).setSeconds(0).setMinutes(0).setHours(0);
};

function calculate_days_old_from_time(time, today) {
    const start_of_today = set_to_start_of_day(today ? today.clone() : new XDate());
    const start_of_other_day = set_to_start_of_day(time.clone());
    const days_old = Math.round(start_of_other_day.diffDays(start_of_today));
    const is_older_year = start_of_today.getFullYear() - start_of_other_day.getFullYear() > 0;

    return {days_old, is_older_year};
}

// Given an XDate object 'time', returns an object:
// {
//      time_str:        a string for the current human-formatted version
//      formal_time_str: a string for the current formally formatted version
//                          e.g. "Monday, April 15, 2017"
//      needs_update:    a boolean for if it will need to be updated when the
//                       day changes
// }
exports.render_now = function (time, today) {
    let time_str = "";
    let needs_update = false;
    // render formal time to be used as title attr tooltip
    // "\xa0" is U+00A0 NO-BREAK SPACE.
    // Can't use &nbsp; as that represents the literal string "&nbsp;".
    const formal_time_str = time.toString("dddd,\u00A0MMMM\u00A0d,\u00A0yyyy");

    // How many days old is 'time'? 0 = today, 1 = yesterday, 7 = a
    // week ago, -1 = tomorrow, etc.

    // Presumably the result of diffDays will be an integer in this
    // case, but round it to be sure before comparing to integer
    // constants.
    const {days_old, is_older_year} = calculate_days_old_from_time(time, today);

    if (days_old === 0) {
        time_str = i18n.t("Today");
        needs_update = true;
    } else if (days_old === 1) {
        time_str = i18n.t("Yesterday");
        needs_update = true;
    } else if (is_older_year) {
        // For long running servers, searching backlog can get ambiguous
        // without a year stamp. Only show year if message is from an older year
        time_str = time.toString("MMM\u00A0dd,\u00A0yyyy");
        needs_update = false;
    } else {
        // For now, if we get a message from tomorrow, we don't bother
        // rewriting the timestamp when it gets to be tomorrow.
        time_str = time.toString("MMM\u00A0dd");
        needs_update = false;
    }
    return {
        time_str,
        formal_time_str,
        needs_update,
    };
};

// Current date is passed as an argument for unit testing
exports.last_seen_status_from_date = function (last_active_date, current_date) {
    if (typeof current_date === "undefined") {
        current_date = new XDate();
    }

    const minutes = Math.floor(last_active_date.diffMinutes(current_date));
    if (minutes <= 2) {
        return i18n.t("Just now");
    }
    if (minutes < 60) {
        return i18n.t("__minutes__ minutes ago", {minutes});
    }
    const {days_old, is_older_year} = calculate_days_old_from_time(last_active_date, current_date);
    const hours = Math.floor(minutes / 60);

    if (days_old === 0) {
        if (hours === 1) {
            return i18n.t("An hour ago");
        }
        return i18n.t("__hours__ hours ago", {hours});
    }

    if (days_old === 1) {
        return i18n.t("Yesterday");
    }

    if (days_old < 90) {
        return i18n.t("__days_old__ days ago", {days_old});
    } else if (days_old > 90 && days_old < 365 && !is_older_year) {
        // Online more than 90 days ago, in the same year
        return i18n.t("__last_active_date__", {
            last_active_date: last_active_date.toString("MMM\u00A0dd"),
        });
    }
    return i18n.t("__last_active_date__", {
        last_active_date: last_active_date.toString("MMM\u00A0dd,\u00A0yyyy"),
    });
};

// List of the dates that need to be updated when the day changes.
// Each timestamp is represented as a list of length 2:
//   [id of the span element, XDate representing the time]
let update_list = [];

// The time at the beginning of the next day, when the timestamps are updated.
// Represented as an XDate with hour, minute, second, millisecond 0.
let next_update;
exports.initialize = function () {
    next_update = set_to_start_of_day(new XDate()).addDays(1);
};

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
        const pieces = [
            '<i class="date-direction fa fa-caret-up"></i>',
            rendered_time_above.time_str,
            '<hr class="date-line">',
            '<i class="date-direction fa fa-caret-down"></i>',
            rendered_time.time_str,
        ];
        elem.append(pieces);
        return elem;
    }
    elem.append(rendered_time.time_str);
    return elem.attr("title", rendered_time.formal_time_str);
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
    const className = "timerender" + next_timerender_id;
    next_timerender_id += 1;
    const rendered_time = exports.render_now(time, today);
    let node = $("<span />").attr("class", className);
    if (time_above !== undefined) {
        const rendered_time_above = exports.render_now(time_above, today);
        node = render_date_span(node, rendered_time, rendered_time_above);
    } else {
        node = render_date_span(node, rendered_time);
    }
    maybe_add_update_list_entry({
        needs_update: rendered_time.needs_update,
        className,
        time,
        time_above,
    });
    return node;
};

// Renders the timestamp returned by the <time:> Markdown syntax.
exports.render_markdown_timestamp = function (time, text) {
    const hourformat = page_params.twenty_four_hour_time ? "HH:mm" : "h:mm a";
    const timestring = format(time, "E, MMM d yyyy, " + hourformat);
    const titlestring = "This time is in your timezone. Original text was '" + text + "'.";
    return {
        text: timestring,
        title: titlestring,
    };
};

// This isn't expected to be called externally except manually for
// testing purposes.
exports.update_timestamps = function () {
    const now = new XDate();
    if (now >= next_update) {
        const to_process = update_list;
        update_list = [];

        for (const entry of to_process) {
            const className = entry.className;
            const elements = $(`.${CSS.escape(className)}`);
            // The element might not exist any more (because it
            // was in the zfilt table, or because we added
            // messages above it and re-collapsed).
            if (elements !== null) {
                for (const element of elements) {
                    const time = entry.time;
                    const time_above = entry.time_above;
                    const rendered_time = exports.render_now(time);
                    if (time_above) {
                        const rendered_time_above = exports.render_now(time_above);
                        render_date_span($(element), rendered_time, rendered_time_above);
                    } else {
                        render_date_span($(element), rendered_time);
                    }
                    maybe_add_update_list_entry({
                        needs_update: rendered_time.needs_update,
                        className,
                        time,
                        time_above,
                    });
                }
            }
        }

        next_update = set_to_start_of_day(now.clone().addDays(1));
    }
};

setInterval(exports.update_timestamps, 60 * 1000);

// Transform a Unix timestamp into a ISO 8601 formatted date string.
//   Example: 1978-10-31T13:37:42Z
exports.get_full_time = function (timestamp) {
    return new XDate(timestamp * 1000).toISOString();
};

exports.get_timestamp_for_flatpickr = (timestring) => {
    let timestamp;
    try {
        // If there's already a valid time in the compose box,
        // we use it to initialize the flatpickr instance.
        timestamp = parseISO(timestring);
    } finally {
        // Otherwise, default to showing the current time.
        if (!timestamp || !isValid(timestamp)) {
            timestamp = new Date();
        }
    }
    return timestamp;
};

exports.stringify_time = function (time) {
    if (page_params.twenty_four_hour_time) {
        return time.toString("HH:mm");
    }
    return time.toString("h:mm TT");
};

// this is for rendering absolute time based off the preferences for twenty-four
// hour time in the format of "%mmm %d, %h:%m %p".
exports.absolute_time = (function () {
    const MONTHS = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ];

    const fmt_time = function (date, H_24) {
        const payload = {
            hours: date.getHours(),
            minutes: date.getMinutes(),
        };

        if (payload.hours > 12 && !H_24) {
            payload.hours -= 12;
            payload.is_pm = true;
        }

        let str = ("0" + payload.hours).slice(-2) + ":" + ("0" + payload.minutes).slice(-2);

        if (!H_24) {
            str += payload.is_pm ? " PM" : " AM";
        }

        return str;
    };

    return function (timestamp, today) {
        if (typeof today === "undefined") {
            today = new Date();
        }
        const date = new Date(timestamp);
        const is_older_year = today.getFullYear() - date.getFullYear() > 0;
        const H_24 = page_params.twenty_four_hour_time;
        let str = MONTHS[date.getMonth()] + " " + date.getDate();
        // include year if message date is from a previous year
        if (is_older_year) {
            str += ", " + date.getFullYear();
        }
        str += " " + fmt_time(date, H_24);
        return str;
    };
})();

exports.get_full_datetime = function (time) {
    // Convert to number of hours ahead/behind UTC.
    // The sign of getTimezoneOffset() is reversed wrt
    // the conventional meaning of UTC+n / UTC-n
    const tz_offset = -time.getTimezoneOffset() / 60;
    return {
        date: time.toLocaleDateString(),
        time: time.toLocaleTimeString() + " (UTC" + (tz_offset < 0 ? "" : "+") + tz_offset + ")",
    };
};

// XDate.toLocaleDateString and XDate.toLocaleTimeString are
// expensive, so we delay running the following code until we need
// the full date and time strings.
exports.set_full_datetime = function timerender_set_full_datetime(message, time_elem) {
    if (message.full_date_str !== undefined) {
        return;
    }

    const time = new XDate(message.timestamp * 1000);
    const full_datetime = exports.get_full_datetime(time);

    message.full_date_str = full_datetime.date;
    message.full_time_str = full_datetime.time;

    time_elem.attr("title", message.full_date_str + " " + message.full_time_str);
};

window.timerender = exports;
