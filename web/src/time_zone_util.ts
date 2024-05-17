const parsable_formats = new Map<string, Intl.DateTimeFormat>();

function get_parsable_format(time_zone: string): Intl.DateTimeFormat {
    let format = parsable_formats.get(time_zone);
    if (format === undefined) {
        format = new Intl.DateTimeFormat("en-US", {
            year: "numeric",
            month: "numeric",
            day: "numeric",
            hour: "numeric",
            minute: "numeric",
            second: "numeric",
            hourCycle: "h23",
            timeZone: time_zone,
        });
        parsable_formats.set(time_zone, format);
    }
    return format;
}

/** Get the given time zone's offset in milliseconds at the given date. */
export function get_offset(date: number | Date, time_zone: string): number {
    const parts = Object.fromEntries(
        get_parsable_format(time_zone)
            .formatToParts(date)
            .map((part) => [part.type, part.value]),
    );
    return (
        Date.UTC(
            Number(parts.year),
            Number(parts.month) - 1,
            Number(parts.day),
            Number(parts.hour),
            Number(parts.minute),
            Number(parts.second),
        ) -
        (Number(date) - (Number(date) % 1000))
    );
}

/** Get the start of the day for the given date in the given time zone. */
export function start_of_day(date: number | Date, time_zone: string): Date {
    const offset = get_offset(date, time_zone);
    let t = Number(date) + offset;
    t -= t % 86400000;
    return new Date(t - get_offset(new Date(t - offset), time_zone));
}

/** Get the number of calendar days between the given dates (ignoring times) in
 * the given time zone. */
export function difference_in_calendar_days(
    left: number | Date,
    right: number | Date,
    time_zone: string,
): number {
    return Math.round(
        (start_of_day(left, time_zone).getTime() - start_of_day(right, time_zone).getTime()) /
            86400000,
    );
}

/** Are the given dates in the same day in the given time zone? */
export function is_same_day(left: number | Date, right: number | Date, time_zone: string): boolean {
    return start_of_day(left, time_zone).getTime() === start_of_day(right, time_zone).getTime();
}
