"use strict";

const assert = require("node:assert/strict");

const {clock, mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");

const common = mock_esm("../src/common");
const date_util = zrequire("date_util");

run_test("get_default_search_suggestions", () => {
    const today = new Date("2024-01-15T12:00:00Z");
    clock.setSystemTime(today.getTime());

    common.phrase_match = (query, value) => value.toLowerCase().includes(query.toLowerCase());

    // Empty query matches both suggestions.
    let suggestions = date_util.get_default_search_suggestions("");
    const [today_suggestion, yesterday_suggestion] = suggestions;

    const today_date_str = today.toISOString().split("T")[0];
    assert.equal(today_suggestion, `date:${today_date_str}`);

    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    const yesterday_date_str = yesterday.toISOString().split("T")[0];
    assert.equal(yesterday_suggestion, `date:${yesterday_date_str}`);

    // Query that matches only today.
    suggestions = date_util.get_default_search_suggestions("tod");
    assert.deepEqual(suggestions, [`date:${today_date_str}`]);

    // Query that matches only yesterday.
    suggestions = date_util.get_default_search_suggestions("yest");
    assert.deepEqual(suggestions, [`date:${yesterday_date_str}`]);

    // Non-matching query returns empty.
    suggestions = date_util.get_default_search_suggestions("foo");
    assert.deepEqual(suggestions, []);

    clock.reset();
});

run_test("get_search_pill_value", () => {
    // Non-date operand is returned as-is.
    assert.equal(date_util.get_search_pill_value("not-a-date"), "not-a-date");

    const today = new Date();
    const today_str = today.toISOString().split("T")[0];
    assert.equal(date_util.get_search_pill_value(today_str), "today");

    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);
    const yesterday_str = yesterday.toISOString().split("T")[0];
    assert.equal(date_util.get_search_pill_value(yesterday_str), "yesterday");

    // Some other valid date should be returned unchanged.
    assert.equal(date_util.get_search_pill_value("2000-01-01"), "2000-01-01");
});

run_test("is_date_str_valid", () => {
    assert.ok(date_util.is_date_str_valid("2024-01-01"));
    assert.ok(date_util.is_date_str_valid("1999-12-31"));

    assert.ok(!date_util.is_date_str_valid("not-a-date"));
    assert.ok(!date_util.is_date_str_valid("2024-13-01"));
    assert.ok(!date_util.is_date_str_valid(""));
    assert.ok(!date_util.is_date_str_valid("today"));
    assert.ok(!date_util.is_date_str_valid("yesterday"));
});

run_test("get_unix_seconds_for_local_midnight", () => {
    const now = new Date("2024-03-10T15:30:00Z");
    clock.setSystemTime(now.getTime());

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

    blueslip.expect("error", "Invalid date string provided");
    const bad_result = date_util.get_unix_seconds_for_local_midnight("invalid-date");
    assert.equal(typeof bad_result, "number");
});
