import {
    format,
    getUnixTime,
    isValid,
    parse,
    parseISO,
    startOfDay,
    subDays,
    subMonths,
    subWeeks,
} from "date-fns";

import * as common from "./common.ts";
import type {Suggestion} from "./search_suggestion.ts";

function get_default_dates(): {
    today: Date;
    yesterday: Date;
    day_before_yesterday: Date;
    a_week_ago: Date;
    a_month_ago: Date;
} {
    const today = new Date();
    const yesterday = subDays(today, 1);
    const day_before_yesterday = subDays(today, 2);
    const a_week_ago = subWeeks(today, 1);
    const a_month_ago = subMonths(today, 1);
    return {today, yesterday, day_before_yesterday, a_week_ago, a_month_ago};
}

type DefaultDates = "today" | "yesterday" | "day_before_yesterday" | "a_week_ago" | "a_month_ago";
type DateSuggestion = {
    operand: string;
    search_pill_value: string;
    date: Date;
};

export function get_default_suggestions(): Record<DefaultDates, DateSuggestion> {
    const {today, yesterday, day_before_yesterday, a_week_ago, a_month_ago} = get_default_dates();
    const default_suggestions: Record<DefaultDates, DateSuggestion> = {
        today: {
            operand: format(today, "yyyy-MM-dd"),
            search_pill_value: "today",
            date: today,
        },
        yesterday: {
            operand: format(yesterday, "yyyy-MM-dd"),
            search_pill_value: "yesterday",
            date: yesterday,
        },
        day_before_yesterday: {
            operand: format(day_before_yesterday, "yyyy-MM-dd"),
            search_pill_value: format(day_before_yesterday, "yyyy-MM-dd"),
            date: day_before_yesterday,
        },
        a_week_ago: {
            operand: format(a_week_ago, "yyyy-MM-dd"),
            search_pill_value: "a week ago",
            date: a_week_ago,
        },
        a_month_ago: {
            operand: format(a_month_ago, "yyyy-MM-dd"),
            search_pill_value: "a month ago",
            date: a_month_ago,
        },
    };
    return default_suggestions;
}

export function get_default_search_suggestions(search_pill_query?: string): Suggestion[] {
    const default_suggestions = Object.values(get_default_suggestions());
    if (search_pill_query === undefined) {
        return default_suggestions.map((suggestion) => `date:${suggestion.operand}`);
    }

    const filtered_suggestions = default_suggestions.filter((suggestion) =>
        common.phrase_match(search_pill_query, suggestion.search_pill_value),
    );

    return filtered_suggestions.map((suggestion) => `date:${suggestion.operand}`);
}

export function get_matching_default_date_suggestions(operand: string): string[] {
    if (operand === "") {
        // For an empty operand, we show all the default suggestions.
        return get_default_search_suggestions();
    }

    const dates = get_default_dates();
    const date_strings = new Set<string>();
    const filtered_default_suggestions = new Set<string>();
    for (const date of Object.values(dates)) {
        const parsed_date = try_match_operand_with_date(operand, date);
        if (parsed_date !== undefined) {
            date_strings.add(format(parsed_date, "yyyy-MM-dd"));
        } else {
            // If the operand cannot be parsed to a date, check whether
            // the operand matches the search pill values for suggestions.
            for (const suggestion of get_default_search_suggestions(operand)) {
                filtered_default_suggestions.add(suggestion);
            }
        }
    }
    const date_suggestions = [...date_strings].map((date_str) => `date:${date_str}`);
    return [...date_suggestions, ...filtered_default_suggestions];
}

// The goal here is to keep matching a potentially half-formed
// operand with the target date until it diverts explicitly.
// When it diverts, we just switch to using "01" for the
// day and month, if those parts are absent.
export function try_match_operand_with_date(operand: string, target_date: Date): Date | undefined {
    const cleaned_operand = operand.replace(/-+$/, "");
    if (cleaned_operand.length === 0) {
        return undefined;
    }

    const operand_parts = cleaned_operand.split("-");
    const [year_part = "", month_part = "", day_part = ""] = operand_parts;
    const target_year = format(target_date, "yyyy");
    const target_month = format(target_date, "MM");
    const target_day = format(target_date, "dd");

    let is_still_matching_target_date = true;

    function get_final_segment(info: {
        segment_type: "year" | "month" | "day";
        current_part: string;
        target_part: string;
    }): string {
        const {target_part, current_part, segment_type} = info;

        // Every date string has three parts: year, month and day and we
        // assume that the caller will generate the final string in that order.
        // If the `current_part` is empty and the previous part(s) matched
        // with the target_date, coerce this part to also match its corresponding target_part
        // in the target date.
        //
        // `is_still_matching_target_date` is true initially;
        // so an empty year segment is converted to the target year.
        // For empty month/day, we choose to default to "01".
        if (current_part.length === 0) {
            if (segment_type === "year" || is_still_matching_target_date) {
                return target_part;
            }
            return "01";
        }

        // Prefer matching with the target_part, instead of the fallback values for
        // year/month/day parts if we are still in the race of matching up with the target_date.
        if (is_still_matching_target_date && target_part.startsWith(current_part)) {
            return target_part;
        }

        // We were unable to match the current_part with the target_part, so
        // we we now go into fall back mode for this part, and the possible remaining
        // parts during subsequent calls.
        is_still_matching_target_date = false;

        if (segment_type === "year") {
            return current_part.padEnd(4, "0");
        }

        if (
            ["month", "day"].includes(segment_type) &&
            current_part.length === 1 &&
            current_part.startsWith("0")
        ) {
            // This is a special case where we cannot end up forming
            // `2010-00-00` for something like
            // current_part = "0" and segment_type="day"/"month".
            return "01";
        }
        return current_part.padEnd(2, "0");
    }

    const final_year = get_final_segment({
        segment_type: "year",
        current_part: year_part,
        target_part: target_year,
    });

    const final_month = get_final_segment({
        segment_type: "month",
        current_part: month_part,
        target_part: target_month,
    });

    const final_day = get_final_segment({
        segment_type: "day",
        current_part: day_part,
        target_part: target_day,
    });

    const final_date_string = `${final_year}-${final_month}-${final_day}`;
    const parsed_date = parseISO(final_date_string);

    // This is mostly meant for the bounds check
    // is_date_valid offers us.
    if (is_date_valid(parsed_date)) {
        return parsed_date;
    }
    return undefined;
}

export function maybe_get_parsed_iso_8601_date(date_str: string): Date | undefined {
    const expected_format = "yyyy-MM-dd";
    const parsed = parse(date_str, expected_format, new Date());

    // The date_str must strictly follow the expected_format, to prevent
    // allowing dates like `2026-1-1` which cause all sorts of edge cases.
    if (isValid(parsed) && format(parsed, expected_format) === date_str) {
        return parsed;
    }
    return undefined;
}

// A date string like "2022-03-10" would return "March 10, 2022"
export function convert_date_str_to_description_date(date_str: string): string {
    const date = parseISO(date_str);
    return isValid(date) ? format(date, "MMMM d, yyyy") : date_str;
}

function is_same_day(d1: Date, d2: Date): boolean {
    return (
        d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate()
    );
}

export function get_search_pill_value(operand: string): string {
    const op_date = parseISO(operand);
    if (!isValid(op_date)) {
        return operand;
    }

    const {today, yesterday, a_month_ago, a_week_ago, day_before_yesterday} =
        get_default_suggestions();
    if (is_same_day(op_date, today.date)) {
        return "today";
    }
    if (is_same_day(op_date, yesterday.date)) {
        return "yesterday";
    }
    if (is_same_day(op_date, day_before_yesterday.date)) {
        return format(op_date, "yyyy-MM-dd");
    }
    if (is_same_day(op_date, a_month_ago.date)) {
        return "a month ago";
    }
    if (is_same_day(op_date, a_week_ago.date)) {
        return "a week ago";
    }

    return operand;
}

export function is_date_valid(date: Date | undefined): boolean {
    return (
        date !== undefined &&
        isValid(date) &&
        // 1970 is the year of the unix epoch; anything earlier
        // predates timestamps we'd ever have messages for.
        date.getFullYear() >= 1970 &&
        date.getFullYear() <= new Date().getFullYear()
    );
}

export function get_unix_seconds_for_local_midnight(date_str?: string): number | null {
    let date: Date;

    if (date_str) {
        date = parseISO(date_str);
    } else {
        date = new Date();
    }

    if (!isValid(date)) {
        return null;
    }

    const midnight = startOfDay(date);
    return getUnixTime(midnight);
}

// Returns the {anchor, anchor_date} pair for fetching messages
// around a calendar-day operand like "2024-01-15". `anchor_date`
// is a UTC ISO string for the user's local midnight on that day,
// since the server expects an unambiguous instant. Returns
// undefined when the operand is not a parseable date.
export function maybe_get_date_anchor(
    operand: string,
): {anchor: "date"; anchor_date: string} | undefined {
    const unix_seconds = get_unix_seconds_for_local_midnight(operand);
    if (unix_seconds === null) {
        return undefined;
    }
    return {
        anchor: "date",
        anchor_date: new Date(unix_seconds * 1000).toISOString(),
    };
}
