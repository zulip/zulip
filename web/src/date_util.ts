import * as blueslip from "./blueslip.ts";
import * as common from "./common.ts";
import type {Suggestion} from "./search_suggestion.ts";

export function get_default_search_suggestions(query: string): Suggestion[] {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const default_suggestions = [
        {operator: "date", operand: today.toISOString().split("T")[0]!, search_pill_value: "today"},
        {
            operator: "date",
            operand: yesterday.toISOString().split("T")[0]!,
            search_pill_value: "yesterday",
        },
    ];

    return default_suggestions
        .filter((suggestion) => common.phrase_match(query, suggestion.search_pill_value))
        .map((suggestion) => `date:${suggestion.operand}`);
}

function is_same_day(d1: Date, d2: Date): boolean {
    return (
        d1.getFullYear() === d2.getFullYear() &&
        d1.getMonth() === d2.getMonth() &&
        d1.getDate() === d2.getDate()
    );
}

export function get_search_pill_value(operand: string): string {
    const op_date = new Date(operand);
    if (Number.isNaN(op_date.getTime())) {
        return operand;
    }

    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);

    if (is_same_day(op_date, today)) {
        return "today";
    }
    if (is_same_day(op_date, yesterday)) {
        return "yesterday";
    }

    return operand;
}

export function is_date_str_valid(date_str: string): boolean {
    return !Number.isNaN(new Date(date_str).getTime());
}

export function get_unix_seconds_for_local_midnight(date_str?: string): number {
    const date = date_str ? new Date(date_str) : new Date();
    date.setHours(0, 0, 0, 0);
    const seconds = date.getTime() / 1000;

    if (Number.isNaN(seconds)) {
        blueslip.error("Invalid date string provided");
    }

    return Math.floor(seconds);
}
