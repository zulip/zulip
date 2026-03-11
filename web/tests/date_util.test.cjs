"use strict";

const assert = require("node:assert/strict");

const {format, startOfDay, getUnixTime, parseISO, isEqual} = require("date-fns");

const {clock, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const date_util = zrequire("date_util");

run_test("get_default_search_suggestions", () => {
    const today = new Date(2024, 0, 15, 2, 0, 0);
    clock.setSystemTime(today.getTime());

    const suggestions = date_util.get_default_search_suggestions();
    const [today_suggestion, yesterday_suggestion, day_before_yesterday_suggestion] = suggestions;

    const today_date_str = format(today, "yyyy-MM-dd");
    assert.equal(today_suggestion, `date:${today_date_str}`);

    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const yesterday_date_str = format(yesterday, "yyyy-MM-dd");
    assert.equal(yesterday_suggestion, `date:${yesterday_date_str}`);

    const day_before_yesterday = new Date();
    day_before_yesterday.setDate(today.getDate() - 2);
    const day_before_yesterday_date_str = format(day_before_yesterday, "yyyy-MM-dd");
    assert.equal(day_before_yesterday_suggestion, `date:${day_before_yesterday_date_str}`);
    clock.reset();
});

run_test("get_sensible_date", () => {
    const today = new Date(2026, 0, 15, 2, 0, 0);
    clock.setSystemTime(today.getTime());
    assert.equal(date_util.get_sensible_date("2030-01-01"), "2026-01-15");
    assert.equal(date_util.get_sensible_date("1950-01-01"), "2026-01-15");
    assert.equal(
        date_util.get_sensible_date("invalid-date-strmaybe_get_parsed_iso_8601_date"),
        "2026-01-15",
    );
    assert.equal(date_util.get_sensible_date("2020"), "2020-01-01");
    clock.reset();
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

    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    const yesterday_str = format(yesterday, "yyyy-MM-dd");
    assert.equal(date_util.get_search_pill_value(yesterday_str), "yesterday");

    // Some other valid date should be returned unchanged.
    assert.equal(date_util.get_search_pill_value("2000-01-01"), "2000-01-01");
});

run_test("is_date_str_valid", () => {
    const today = new Date(2026, 0, 15, 2, 0, 0);
    clock.setSystemTime(today.getTime());
    assert.ok(date_util.is_date_str_valid("2024-01-01"));
    assert.ok(date_util.is_date_str_valid("2008-12-31"));

    assert.ok(!date_util.is_date_str_valid("not-a-date"));
    assert.ok(!date_util.is_date_str_valid("2024-13-01"));
    assert.ok(!date_util.is_date_str_valid(""));
    assert.ok(!date_util.is_date_str_valid("today"));
    assert.ok(!date_util.is_date_str_valid("yesterday"));
    clock.reset();
});

run_test("convert_date_str_to_description_text", () => {
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
