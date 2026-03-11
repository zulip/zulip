import {format, getUnixTime, isValid, parse, parseISO, startOfDay} from "date-fns";

import type {Suggestion} from "./search_suggestion.ts";

export function get_default_search_suggestions(): Suggestion[] {
    const today = new Date();
    const yesterday = new Date();
    const day_before_yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    day_before_yesterday.setDate(today.getDate() - 2);

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

// The main aim here is to return a well formatted ISO 8601 date string
// in the `yyyy-MM-dd` format if the parsed `date_str` against that format
// is valid. Otherwise we return a formatted string for today.
export function get_sensible_date(date_str: string): string {
    const op_date = parseISO(date_str);
    if (
        !isValid(op_date) ||
        op_date.getFullYear() < 2000 ||
        op_date.getFullYear() > new Date().getFullYear()
    ) {
        const today = new Date();
        return format(today, "yyyy-MM-dd");
    }
    return format(op_date, "yyyy-MM-dd");
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

    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

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
