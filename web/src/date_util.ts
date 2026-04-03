import {format, getUnixTime, isValid, parse, parseISO, startOfDay} from "date-fns";

import type {Suggestion} from "./search_suggestion.ts";

function get_default_dates(): {today: Date; yesterday: Date; day_before_yesterday: Date} {
    const today = new Date();
    const yesterday = new Date();
    const day_before_yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    day_before_yesterday.setDate(today.getDate() - 2);
    return {today, yesterday, day_before_yesterday};
}

export function get_default_search_suggestions(): Suggestion[] {
    const {today, yesterday, day_before_yesterday} = get_default_dates();
    const default_suggestions = [
        {
            operator: "date",
            operand: format(today, "yyyy-MM-dd"),
            search_pill_value: "today",
        },
        {
            operator: "date",
            operand: format(yesterday, "yyyy-MM-dd"),
            search_pill_value: "yesterday",
        },
        {
            operator: "date",
            operand: format(day_before_yesterday, "yyyy-MM-dd"),
        },
    ];

    return default_suggestions.map((suggestion) => `date:${suggestion.operand}`);
}

export function get_suggestions_via_smart_parsing(operand: string): string[] {
    if (operand === "") {
        // For an empty operand, we show all the default suggestions.
        return get_default_search_suggestions();
    }

    const dates = get_default_dates();
    const date_strings = new Set<string>();
    for (const date of Object.values(dates)) {
        const parsed_date = try_smart_parse_date_operand(operand, date);
        if (parsed_date !== undefined) {
            date_strings.add(format(parsed_date, "yyyy-MM-dd"));
        }
    }
    return [...date_strings].map((date_str) => `date:${date_str}`);
}

// The goal here is to keep matching a potentially half-formed
// operand with the target date until it diverts explicitly.
// When it diverts, we just switch to using "01" for the
// day and month, if those parts are absent.
export function try_smart_parse_date_operand(operand: string, target_date: Date): Date | undefined {
    const cleaned_operand = operand.replace(/-+$/, "");
    if (cleaned_operand.length === 0) {
        return undefined;
    }

    const operand_parts = cleaned_operand.split("-");
    const [year_part = "", month_part = "", day_part = ""] = operand_parts;
    const target_year = format(target_date, "yyyy");
    const target_month = format(target_date, "MM");
    const target_day = format(target_date, "dd");

    let final_year = "0000";
    let final_month = "01";
    let final_day = "01";

    let is_still_matching_target = true;
    if (year_part) {
        if (is_still_matching_target && target_year.startsWith(year_part)) {
            final_year = target_year;
        } else {
            is_still_matching_target = false;
            final_year = year_part.padEnd(4, "0");
        }
    } else {
        final_year = target_year;
    }

    if (month_part) {
        if (is_still_matching_target && target_month.startsWith(month_part)) {
            final_month = target_month;
        } else {
            is_still_matching_target = false;
            if (month_part.length === 1 && month_part.startsWith("0")) {
                final_month = "01";
            } else {
                final_month = month_part.padEnd(2, "0");
            }
        }
    } else {
        final_month = is_still_matching_target ? target_month : "01";
    }

    if (day_part) {
        if (is_still_matching_target && target_day.startsWith(day_part)) {
            final_day = target_day;
        } else {
            if (day_part.length === 1 && day_part.startsWith("0")) {
                final_day = "01";
            } else {
                final_day = day_part.padEnd(2, "0");
            }
        }
    } else {
        final_day = is_still_matching_target ? target_day : "01";
    }

    const final_date_string = `${final_year}-${final_month}-${final_day}`;
    const parsed_date = parseISO(final_date_string);
    if (
        !isValid(parsed_date) ||
        parsed_date.getFullYear() < 2000 ||
        parsed_date.getFullYear() > new Date().getFullYear()
    ) {
        return undefined;
    }
    return parsed_date;
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

    const {today, yesterday} = get_default_dates();
    if (is_same_day(op_date, today)) {
        return "today";
    }
    if (is_same_day(op_date, yesterday)) {
        return "yesterday";
    }

    return operand;
}

export function is_date_str_valid(date_str: string): boolean {
    const date = parseISO(date_str);
    return (
        isValid(date) &&
        date.getFullYear() >= 2000 &&
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
