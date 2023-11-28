import assert from "minimalistic-assert";

const offset_formats = new Map<string, Intl.DateTimeFormat>();

function get_offset_format(time_zone: string): Intl.DateTimeFormat {
    let format = offset_formats.get(time_zone);
    if (format === undefined) {
        format = new Intl.DateTimeFormat("en-US", {
            timeZoneName: "longOffset",
            timeZone: time_zone,
        });
        offset_formats.set(time_zone, format);
    }
    return format;
}

/** Get the given time zone's offset in milliseconds at the given date. */
export function get_offset(date: number | Date, time_zone: string): number {
    const offset_string = get_offset_format(time_zone)
        .formatToParts(date)
        .find((part) => part.type === "timeZoneName")!.value;
    if (offset_string === "GMT") {
        return 0;
    }
    const m = /^GMT(([+-])\d\d):(\d\d)$/.exec(offset_string);
    assert(m !== null, offset_string);
    return (Number(m[1]) * 60 + Number(m[2] + m[3])) * 60000;
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
