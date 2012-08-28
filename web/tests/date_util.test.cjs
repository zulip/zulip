"use strict";

const assert = require("node:assert/strict");

const {
    format,
    startOfDay,
    getUnixTime,
    parseISO,
    isEqual,
    subDays,
    subWeeks,
    subMonths,
} = require("date-fns");

const {clock, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const date_util = zrequire("date_util");

run_test("get_default_search_suggestions", () => {
    const today = new Date(2024, 0, 15, 2, 0, 0);
    clock.setSystemTime(today.getTime());

    const [today_sug, yesterday_sug, day_before_sug, week_ago_sug, month_ago_sug] =
        date_util.get_default_search_suggestions();

    const expected = (date) => `date:${format(date, "yyyy-MM-dd")}`;

    assert.equal(today_sug, expected(today));
    assert.equal(yesterday_sug, expected(subDays(today, 1)));
    assert.equal(day_before_sug, expected(subDays(today, 2)));
    assert.equal(week_ago_sug, expected(subWeeks(today, 1)));
    assert.equal(month_ago_sug, expected(subMonths(today, 1)));

    clock.reset();
});

run_test("get_matching_default_date_suggestions", () => {
    const today = parseISO("2026-03-31");
    clock.setSystemTime(today.getTime());
    const default_suggestions = {
        today: "date:2026-03-31",
        yesterday: "date:2026-03-30",
        day_before_yesterday: "date:2026-03-29",
        a_week_ago: "date:2026-03-24",
        a_month_ago: "date:2026-02-28",
    };

    // Partially matching dates must give back default suggestions
    assert.deepEqual(
        date_util.get_matching_default_date_suggestions("20"),
        Object.values(default_suggestions),
    );

    assert.deepEqual(
        date_util.get_matching_default_date_suggestions("2026"),
        Object.values(default_suggestions),
    );

    assert.deepEqual(date_util.get_matching_default_date_suggestions("2026-03-3"), [
        "date:2026-03-31",
        "date:2026-03-30",
    ]);

    // Empty operand should give back all default suggestions
    assert.deepEqual(
        date_util.get_matching_default_date_suggestions(""),
        Object.values(default_suggestions),
    );

    // For coverage.
    assert.deepEqual(date_util.get_matching_default_date_suggestions("-"), []);

    assert.deepEqual(date_util.get_matching_default_date_suggestions("-01-01"), [
        "date:2026-01-01",
    ]);

    // Get suggestions for trailing hyphens/zeros
    assert.deepEqual(
        date_util.get_matching_default_date_suggestions("2026-"),
        Object.values(default_suggestions),
    );

    assert.deepEqual(
        date_util.get_matching_default_date_suggestions("2026-0"),
        Object.values(default_suggestions),
    );

    // operand which doesn't match any default suggestions and pill labels.
    assert.deepEqual(date_util.get_matching_default_date_suggestions("2023-02"), [
        "date:2023-02-01",
    ]);
    assert.deepEqual(date_util.get_matching_default_date_suggestions("2023-02-0"), [
        "date:2023-02-01",
    ]);
    assert.deepEqual(date_util.get_matching_default_date_suggestions("2023-0-"), [
        "date:2023-01-01",
    ]);
    assert.deepEqual(date_util.get_matching_default_date_suggestions("2023"), ["date:2023-01-01"]);

    // operand doesn't match any default suggestions but matches pill labels.
    assert.deepEqual(date_util.get_matching_default_date_suggestions("to"), [
        default_suggestions.today,
    ]);
    assert.deepEqual(date_util.get_matching_default_date_suggestions("a "), [
        default_suggestions.a_week_ago,
        default_suggestions.a_month_ago,
    ]);
    assert.deepEqual(date_util.get_matching_default_date_suggestions("month"), [
        default_suggestions.a_month_ago,
    ]);

    // Gibberish shouldn't yield any suggestions
    assert.deepEqual(date_util.get_matching_default_date_suggestions("lkmvlckakj"), []);
});

run_test("maybe_get_parsed_iso_8601_date", () => {
    const d1 = date_util.maybe_get_parsed_iso_8601_date("2026-03-28");
    assert.ok(isEqual(d1, parseISO("2026-03-28")));
    const d2 = date_util.maybe_get_parsed_iso_8601_date("2026");
    assert.equal(d2, undefined);
    const d3 = date_util.maybe_get_parsed_iso_8601_date("2026-01");
    assert.equal(d3, undefined);
});

run_test("get_search_pill_value", () => {
    // Non-date operand is returned as-is.
    assert.equal(date_util.get_search_pill_value("not-a-date"), "not-a-date");

    const today = new Date();
    const today_str = format(today, "yyyy-MM-dd");
    assert.equal(date_util.get_search_pill_value(today_str), "today");

    const yesterday = subDays(today, 1);
    const yesterday_str = format(yesterday, "yyyy-MM-dd");
    assert.equal(date_util.get_search_pill_value(yesterday_str), "yesterday");

    const day_before_yesterday = subDays(today, 2);
    const day_before_yesterday_str = format(day_before_yesterday, "yyyy-MM-dd");
    assert.equal(
        date_util.get_search_pill_value(day_before_yesterday_str),
        day_before_yesterday_str,
    );

    const a_week_ago = subWeeks(today, 1);
    const a_week_ago_str = format(a_week_ago, "yyyy-MM-dd");
    assert.equal(date_util.get_search_pill_value(a_week_ago_str), "a week ago");

    const a_month_ago = subMonths(today, 1);
    const a_month_ago_str = format(a_month_ago, "yyyy-MM-dd");
    assert.equal(date_util.get_search_pill_value(a_month_ago_str), "a month ago");

    // Some other valid date should be returned unchanged.
    assert.equal(date_util.get_search_pill_value("2000-01-01"), "2000-01-01");
});

run_test("is_date_valid", () => {
    const today = new Date(2026, 0, 15, 2, 0, 0);
    clock.setSystemTime(today.getTime());
    assert.ok(date_util.is_date_valid(new Date(2024, 0, 15, 2, 0, 0)));
    assert.ok(date_util.is_date_valid(new Date(2022, 4, 14, 0, 0, 0)));

    assert.ok(!date_util.is_date_valid(undefined));
    assert.ok(!date_util.is_date_valid(new Date(2028, 0, 0, 0, 0, 0)));
    assert.ok(!date_util.is_date_valid(new Date(1500, 0, 0, 0, 0, 0)));
    clock.reset();
});

run_test("convert_date_str_to_description_date", () => {
    assert.equal(date_util.convert_date_str_to_description_date("2025-05-12"), "May 12, 2025");
    assert.equal(date_util.convert_date_str_to_description_date("foobar"), "foobar");
});

run_test("get_unix_seconds_for_local_midnight", () => {
    const now = new Date(2026, 2, 10, 15, 30, 0);
    clock.setSystemTime(now.getTime());

    const expected_ts = getUnixTime(startOfDay(now));

    assert.equal(date_util.get_unix_seconds_for_local_midnight(), expected_ts);

    // When no argument is given, we use "today" based on local time and zero out HH:MM:SS.
    const local_now = new Date();
    const expected_midnight = new Date(local_now);
    expected_midnight.setHours(0, 0, 0, 0);
    assert.equal(
        date_util.get_unix_seconds_for_local_midnight(),
        Math.floor(expected_midnight.getTime() / 1000),
    );

    // With an explicit date string.
    const some_date_str = "2024-02-20";
    const ts = date_util.get_unix_seconds_for_local_midnight(some_date_str);
    const round_tripped = new Date(ts * 1000);
    assert.equal(round_tripped.getFullYear(), 2024);
    assert.equal(round_tripped.getMonth(), 1);
    assert.equal(round_tripped.getDate(), 20);
    assert.equal(round_tripped.getHours(), 0);
    assert.equal(round_tripped.getMinutes(), 0);
    assert.equal(round_tripped.getSeconds(), 0);

    clock.reset();

    const bad_result = date_util.get_unix_seconds_for_local_midnight("invalid-date");
    assert.equal(bad_result, null);
});

run_test("maybe_get_date_anchor", () => {
    const result = date_util.maybe_get_date_anchor("2024-02-20");
    assert.ok(result);
    assert.equal(result.anchor, "date");
    // anchor_date is a UTC ISO string for local midnight on the
    // operand date; verify it round-trips to that local day.
    const parsed = new Date(result.anchor_date);
    assert.equal(parsed.getFullYear(), 2024);
    assert.equal(parsed.getMonth(), 1);
    assert.equal(parsed.getDate(), 20);
    assert.equal(parsed.getHours(), 0);
    assert.equal(parsed.getMinutes(), 0);
    assert.equal(parsed.getSeconds(), 0);

    assert.equal(date_util.maybe_get_date_anchor("invalid-date"), undefined);
});
