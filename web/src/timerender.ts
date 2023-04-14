import {
    differenceInCalendarDays,
    differenceInHours,
    differenceInMinutes,
    format,
    formatISO,
    isEqual,
    isValid,
    parseISO,
    startOfToday,
} from "date-fns";
import $ from "jquery";
import _ from "lodash";

import render_markdown_time_tooltip from "../templates/markdown_time_tooltip.hbs";

import {$t} from "./i18n";
import {parse_html} from "./ui_util";
import {user_settings} from "./user_settings";

let next_timerender_id = 0;

export function clear_for_testing(): void {
    next_timerender_id = 0;
}

type DateFormat = "weekday" | "dayofyear" | "weekday_dayofyear_year" | "dayofyear_year";
type DateWithTimeFormat = "dayofyear_time" | "dayofyear_year_time" | "weekday_dayofyear_year_time";
type TimeFormat = "time" | "time_sec";

type DateOrTimeFormat = DateFormat | TimeFormat | DateWithTimeFormat;

// Translates Zulip-specific format names, documented in the comments
// below, into the appropriate options to pass to the Intl library
// along with the user's locale to render date in that style of format.
//
// Note that because date/time formats vary with locale, the below
// examples are what a user with English as their language will see
// but users in other locales will see something different, especially
// for any formats that display the name for a month/weekday, but
// possibly in more subtle ways for languages with different
// punctuation schemes for date and times.
function get_format_options_for_type(type: DateOrTimeFormat): Intl.DateTimeFormatOptions {
    const is_twenty_four_hour_time = user_settings.twenty_four_hour_time;

    const time_format_options: Intl.DateTimeFormatOptions = is_twenty_four_hour_time
        ? {hourCycle: "h23", hour: "2-digit", minute: "2-digit"}
        : {
              hourCycle: "h12",
              hour: "numeric",
              minute: "2-digit",
          };

    const weekday_format_options: Intl.DateTimeFormatOptions = {weekday: "long"};
    const full_format_options: Intl.DateTimeFormatOptions = {dateStyle: "full"};

    const dayofyear_format_options: Intl.DateTimeFormatOptions = {day: "numeric", month: "short"};
    const dayofyear_year_format_options: Intl.DateTimeFormatOptions = {
        ...dayofyear_format_options,
        year: "numeric",
    };
    const long_format_options: Intl.DateTimeFormatOptions = {
        ...dayofyear_year_format_options,
        weekday: "short",
    };

    switch (type) {
        case "time": // 01:30 PM
            return time_format_options;
        case "time_sec": // 01:30:42 PM
            return {...time_format_options, second: "2-digit"};
        case "weekday": // Wednesday
            return weekday_format_options;
        case "dayofyear": // Jul 27
            return dayofyear_format_options;
        case "dayofyear_time": // Jul 27, 01:30 PM
            return {...dayofyear_format_options, ...time_format_options};
        case "dayofyear_year": // Jul 27, 2016
            return dayofyear_year_format_options;
        case "dayofyear_year_time": // Jul 27, 2016, 01:30 PM
            return {...dayofyear_year_format_options, ...time_format_options};
        case "weekday_dayofyear_year": // Wednesday, July 27, 2016
            return full_format_options;
        case "weekday_dayofyear_year_time": // Wed, Jul 27, 2016, 13:30
            return {...long_format_options, ...time_format_options};
        default:
            throw new Error("Wrong format provided.");
    }
}

function get_user_locale(): string {
    const user_default_language = user_settings.default_language;
    let locale = "";
    try {
        locale = Intl.DateTimeFormat.supportedLocalesOf(user_default_language)[0];
    } catch {
        locale = "default";
    }
    return locale;
}

// Common function for all date/time rendering in the project. Handles
// localization using the user's configured locale and the
// twenty_four_hour_time setting.
//
// See get_format_options_for_type for details on the supported formats.
export function get_localized_date_or_time_for_format(
    date: Date | number,
    format: DateOrTimeFormat,
): string {
    const locale = get_user_locale();
    return new Intl.DateTimeFormat(locale, get_format_options_for_type(format)).format(date);
}

// Exported for tests only.
export function get_tz_with_UTC_offset(time: number | Date): string {
    const tz_offset = format(time, "xxx");
    let timezone = new Intl.DateTimeFormat(undefined, {timeZoneName: "short"})
        .formatToParts(time)
        .find(({type}) => type === "timeZoneName")?.value;

    if (timezone === "UTC") {
        return "UTC";
    }

    // When user's locale doesn't match their time zone (eg. en_US for IST),
    // we get `timezone` in the format of'GMT+x:y. We don't want to
    // show that along with (UTC+x:y)
    timezone = /GMT[+-][\d:]*/.test(timezone ?? "") ? "" : timezone;

    const tz_UTC_offset = `(UTC${tz_offset})`;

    if (timezone) {
        return timezone + " " + tz_UTC_offset;
    }
    return tz_UTC_offset;
}

// Given a Date object 'time', returns an object:
// {
//      time_str:        a string for the current human-formatted version
//      formal_time_str: a string for the current formally formatted version
//                          e.g. "Monday, April 15, 2017"
//      needs_update:    a boolean for if it will need to be updated when the
//                       day changes
// }
export type TimeRender = {
    time_str: string;
    formal_time_str: string;
    needs_update: boolean;
};

export function render_now(time: Date, today = new Date()): TimeRender {
    let time_str = "";
    let needs_update = false;
    // render formal time to be used for tippy tooltip
    const formal_time_str = get_localized_date_or_time_for_format(time, "weekday_dayofyear_year");
    // How many days old is 'time'? 0 = today, 1 = yesterday, 7 = a
    // week ago, -1 = tomorrow, etc.

    // Presumably the result of diffDays will be an integer in this
    // case, but round it to be sure before comparing to integer
    // constants.
    const days_old = differenceInCalendarDays(today, time);

    if (days_old === 0) {
        time_str = $t({defaultMessage: "Today"});
        needs_update = true;
    } else if (days_old === 1) {
        time_str = $t({defaultMessage: "Yesterday"});
        needs_update = true;
    } else if (time.getFullYear() !== today.getFullYear()) {
        // For long running servers, searching backlog can get ambiguous
        // without a year stamp. Only show year if message is from an older year
        time_str = get_localized_date_or_time_for_format(time, "dayofyear_year");
        needs_update = false;
    } else {
        // For now, if we get a message from tomorrow, we don't bother
        // rewriting the timestamp when it gets to be tomorrow.
        time_str = get_localized_date_or_time_for_format(time, "dayofyear");
        needs_update = false;
    }
    return {
        time_str,
        formal_time_str,
        needs_update,
    };
}

// Relative time rendering for use in most screens like Recent conversations.
//
// Current date is passed as an argument for unit testing
export function relative_time_string_from_date({
    date,
    current_date = new Date(),
}: {
    date: Date;
    current_date?: Date;
}): string {
    const minutes = differenceInMinutes(current_date, date);
    if (minutes <= 2) {
        return $t({defaultMessage: "Just now"});
    }
    if (minutes < 60) {
        return $t({defaultMessage: "{minutes} minutes ago"}, {minutes});
    }

    const days_old = differenceInCalendarDays(current_date, date);
    const hours = Math.floor(minutes / 60);

    if (hours < 24) {
        if (hours === 1) {
            return $t({defaultMessage: "An hour ago"});
        }
        return $t({defaultMessage: "{hours} hours ago"}, {hours});
    }

    if (days_old === 1) {
        return $t({defaultMessage: "Yesterday"});
    }

    if (days_old < 90) {
        return $t({defaultMessage: "{days_old} days ago"}, {days_old});
    } else if (
        days_old > 90 &&
        days_old < 365 &&
        date.getFullYear() === current_date.getFullYear()
    ) {
        // Online more than 90 days ago, in the same year
        return get_localized_date_or_time_for_format(date, "dayofyear");
    }
    return get_localized_date_or_time_for_format(date, "dayofyear_year");
}

// Relative time logic variant use in the buddy list, where every
// string has "Active" init. This is hard to deduplicate with
// relative_time_string_from_date because of complexities involved in i18n and
// word order.
//
// Current date is passed as an argument for unit testing
export function last_seen_status_from_date(
    last_active_date: Date,
    current_date = new Date(),
): string {
    const minutes = differenceInMinutes(current_date, last_active_date);
    if (minutes < 60) {
        return $t({defaultMessage: "Active {minutes} minutes ago"}, {minutes});
    }

    const days_old = differenceInCalendarDays(current_date, last_active_date);
    const hours = Math.floor(minutes / 60);

    if (hours < 24) {
        if (hours === 1) {
            return $t({defaultMessage: "Active an hour ago"});
        }
        return $t({defaultMessage: "Active {hours} hours ago"}, {hours});
    }

    if (days_old === 1) {
        return $t({defaultMessage: "Active yesterday"});
    }

    if (days_old < 90) {
        return $t({defaultMessage: "Active {days_old} days ago"}, {days_old});
    } else if (
        days_old > 90 &&
        days_old < 365 &&
        last_active_date.getFullYear() === current_date.getFullYear()
    ) {
        // Online more than 90 days ago, in the same year
        return $t(
            {defaultMessage: "Active {last_active_date}"},
            {
                last_active_date: get_localized_date_or_time_for_format(
                    last_active_date,
                    "dayofyear",
                ),
            },
        );
    }
    return $t(
        {defaultMessage: "Active {last_active_date}"},
        {
            last_active_date: get_localized_date_or_time_for_format(
                last_active_date,
                "dayofyear_year",
            ),
        },
    );
}

// List of the dates that need to be updated when the day changes.
// Each timestamp is represented as a list of length 2:
//   [id of the span element, Date representing the time]
type UpdateEntry = {
    needs_update: boolean;
    className: string;
    time: Date;
};
let update_list: UpdateEntry[] = [];

// The time at the beginning of the day, when the timestamps were updated.
// Represented as a Date with hour, minute, second, millisecond 0.
let last_update: Date;

export function initialize(): void {
    last_update = startOfToday();
}

function maybe_add_update_list_entry(entry: UpdateEntry): void {
    if (entry.needs_update) {
        update_list.push(entry);
    }
}

function render_date_span($elem: JQuery, rendered_time: TimeRender): JQuery {
    $elem.text("");
    $elem.append(_.escape(rendered_time.time_str));
    return $elem.attr("data-tippy-content", rendered_time.formal_time_str);
}

// Given an Date object 'time', return a DOM node that initially
// displays the human-formatted date, and is updated automatically as
// necessary (e.g. changing "Today" to "Yesterday" to "Jul 1").

// (What's actually spliced into the message template is the contents
// of this DOM node as HTML, so effectively a copy of the node. That's
// okay since to update the time later we look up the node by its id.)
export function render_date(time: Date, today: Date): JQuery {
    const className = `timerender${next_timerender_id}`;
    next_timerender_id += 1;
    const rendered_time = render_now(time, today);
    let $node = $("<span>").attr("class", className);
    $node = render_date_span($node, rendered_time);
    maybe_add_update_list_entry({
        needs_update: rendered_time.needs_update,
        className,
        time,
    });
    return $node;
}

// Renders the timestamp returned by the <time:> Markdown syntax.
export function format_markdown_time(time: number | Date): string {
    return get_localized_date_or_time_for_format(time, "weekday_dayofyear_year_time");
}

export function get_markdown_time_tooltip(reference: HTMLElement): DocumentFragment | string {
    if (reference instanceof HTMLTimeElement) {
        const time = parseISO(reference.dateTime);
        const tz_offset_str = get_tz_with_UTC_offset(time);
        return parse_html(render_markdown_time_tooltip({tz_offset_str}));
    }
    return "";
}

// This isn't expected to be called externally except manually for
// testing purposes.
export function update_timestamps(): void {
    const today = startOfToday();
    if (!isEqual(today, last_update)) {
        const to_process = update_list;
        update_list = [];

        for (const entry of to_process) {
            const className = entry.className;
            const $elements = $(`.${CSS.escape(className)}`);
            // The element might not exist any more (because it
            // was in the zfilt table, or because we added
            // messages above it and re-collapsed).
            if ($elements.length > 0) {
                const time = entry.time;
                const rendered_time = render_now(time, today);
                for (const element of $elements) {
                    render_date_span($(element), rendered_time);
                }
                maybe_add_update_list_entry({
                    needs_update: rendered_time.needs_update,
                    className,
                    time,
                });
            }
        }

        last_update = today;
    }
}

setInterval(update_timestamps, 60 * 1000);

// Transform a Unix timestamp into a ISO 8601 formatted date string.
//   Example: 1978-10-31T13:37:42Z
export function get_full_time(timestamp: number): string {
    return formatISO(timestamp * 1000);
}

export function get_timestamp_for_flatpickr(timestring: string): Date {
    let timestamp;
    try {
        // If there's already a valid time in the compose box,
        // we use it to initialize the flatpickr instance.
        timestamp = parseISO(timestring);
    } finally {
        // Otherwise, default to showing the current time to the hour.
        if (!timestamp || !isValid(timestamp)) {
            timestamp = new Date();
            timestamp.setMinutes(0, 0);
        }
    }
    return timestamp;
}

export function stringify_time(time: number | Date): string {
    return get_localized_date_or_time_for_format(time, "time");
}

export function format_time_modern(time: number | Date, today = new Date()): string {
    const hours = differenceInHours(today, time);
    const days_old = differenceInCalendarDays(today, time);

    if (time > today) {
        /* For timestamps in the future, we always show the year*/
        return get_localized_date_or_time_for_format(time, "dayofyear_year");
    } else if (hours < 24) {
        return stringify_time(time);
    } else if (days_old === 1) {
        return $t({defaultMessage: "Yesterday"});
    } else if (days_old < 7) {
        return get_localized_date_or_time_for_format(time, "weekday");
    } else if (days_old <= 180) {
        return get_localized_date_or_time_for_format(time, "dayofyear");
    }

    return get_localized_date_or_time_for_format(time, "dayofyear_year");
}

// this is for rendering absolute time based off the preferences for twenty-four
// hour time in the format of "%mmm %d, %h:%m %p".
export function absolute_time(timestamp: number, today = new Date()): string {
    const date = new Date(timestamp);
    const is_older_year = today.getFullYear() - date.getFullYear() > 0;

    return get_localized_date_or_time_for_format(
        date,
        is_older_year ? "dayofyear_year_time" : "dayofyear_time",
    );
}

// Pass time_format="time" to not include seconds in the time format.
export function get_full_datetime(time: Date, time_format: TimeFormat = "time_sec"): string {
    const date_string = get_localized_date_or_time_for_format(time, "dayofyear_year");
    const time_string = get_localized_date_or_time_for_format(time, time_format);
    return $t({defaultMessage: "{date} at {time}"}, {date: date_string, time: time_string});
}

// Preferred variant for displaying a full datetime to users in
// contexts like tooltips, where the time was already displayed to the
// user in a less precise format.
export function get_full_datetime_clarification(
    time: Date,
    time_format: TimeFormat = "time_sec",
): string {
    const locale = get_user_locale();
    const date_string = time.toLocaleDateString(locale);
    let time_string = get_localized_date_or_time_for_format(time, time_format);

    const tz_offset_str = get_tz_with_UTC_offset(time);

    time_string = time_string + " " + tz_offset_str;

    return $t({defaultMessage: "{date} at {time}"}, {date: date_string, time: time_string});
}

type TimeLimitSetting = {
    value: number;
    unit: string;
};

export function get_time_limit_setting_in_appropriate_unit(
    time_limit_in_seconds: number,
): TimeLimitSetting {
    const time_limit_in_minutes = Math.floor(time_limit_in_seconds / 60);
    if (time_limit_in_minutes < 60) {
        return {value: time_limit_in_minutes, unit: "minute"};
    }

    const time_limit_in_hours = Math.floor(time_limit_in_minutes / 60);
    if (time_limit_in_hours < 24) {
        return {value: time_limit_in_hours, unit: "hour"};
    }

    const time_limit_in_days = Math.floor(time_limit_in_hours / 24);
    return {value: time_limit_in_days, unit: "day"};
}

export function should_display_profile_incomplete_alert(timestamp: number): boolean {
    const today = new Date(Date.now());
    const time = new Date(timestamp);
    const days_old = differenceInCalendarDays(today, time);

    if (days_old >= 15) {
        return true;
    }
    return false;
}
