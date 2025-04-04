"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {get_offset, start_of_day, is_same_day, difference_in_calendar_days} =
    zrequire("time_zone_util");

function pre(date) {
    return new Date(date.getTime() - 1);
}

const ny = "America/New_York";
const ny_new_year = new Date("2023-01-01T05:00Z");
const ny_new_year_eve = new Date("2022-12-31T05:00Z");
const st_johns = "America/St_Johns";
const st_johns_dst_begin = new Date("2023-03-12T05:30Z");
const st_johns_dst_end = new Date("2023-11-05T04:30Z");
const chatham = "Pacific/Chatham";
const chatham_dst_begin = new Date("2022-09-24T14:00Z");
const chatham_dst_end = new Date("2023-04-01T14:00Z");
const kiritimati = "Pacific/Kiritimati";
const kiritimati_date_skip = new Date("1994-12-31T10:00Z");
const fractional_date = new Date("2023-01-02T03:04:05.678Z");

run_test("get_offset", () => {
    assert.equal(get_offset(ny_new_year, "UTC"), 0);
    assert.equal(get_offset(ny_new_year, ny), -5 * 60 * 60000);
    assert.equal(get_offset(pre(st_johns_dst_begin), st_johns), -(3 * 60 + 30) * 60000);
    assert.equal(get_offset(st_johns_dst_begin, st_johns), -(2 * 60 + 30) * 60000);
    assert.equal(get_offset(pre(st_johns_dst_end), st_johns), -(2 * 60 + 30) * 60000);
    assert.equal(get_offset(st_johns_dst_end, st_johns), -(3 * 60 + 30) * 60000);
    assert.equal(get_offset(pre(chatham_dst_begin), chatham), (12 * 60 + 45) * 60000);
    assert.equal(get_offset(chatham_dst_begin, chatham), (13 * 60 + 45) * 60000);
    assert.equal(get_offset(pre(chatham_dst_end), chatham), (13 * 60 + 45) * 60000);
    assert.equal(get_offset(chatham_dst_end, chatham), (12 * 60 + 45) * 60000);
    assert.equal(get_offset(pre(kiritimati_date_skip), kiritimati), -10 * 60 * 60000);
    assert.equal(get_offset(kiritimati_date_skip, kiritimati), 14 * 60 * 60000);
    assert.equal(get_offset(fractional_date, "UTC"), 0);
    assert.equal(get_offset(fractional_date, ny), -5 * 60 * 60000);
    assert.equal(get_offset(fractional_date, kiritimati), 14 * 60 * 60000);
});

run_test("start_of_day", () => {
    for (const [date, time_zone] of [
        [pre(ny_new_year), "UTC"],
        [ny_new_year, "UTC"],
        [pre(ny_new_year), ny],
        [ny_new_year, ny],
        [pre(st_johns_dst_begin), st_johns],
        [st_johns_dst_end, st_johns],
        [pre(st_johns_dst_end), st_johns],
        [st_johns_dst_end, st_johns],
        [pre(chatham_dst_begin), chatham],
        [chatham_dst_end, chatham],
        [pre(chatham_dst_end), chatham],
        [chatham_dst_end, chatham],
        [pre(kiritimati_date_skip), kiritimati],
        [kiritimati_date_skip, kiritimati],
    ]) {
        const start = start_of_day(date, time_zone);
        assert.equal(
            start.toLocaleDateString("en-US", {timeZone: time_zone}),
            date.toLocaleDateString("en-US", {timeZone: time_zone}),
        );
        assert.equal(start.toLocaleTimeString("en-US", {timeZone: time_zone}), "12:00:00 AM");
    }
});

run_test("is_same_day", () => {
    assert.ok(is_same_day(pre(ny_new_year), ny_new_year_eve, ny));
    assert.ok(!is_same_day(pre(ny_new_year), ny_new_year, ny));
    assert.ok(is_same_day(pre(st_johns_dst_begin), st_johns_dst_begin, st_johns));
    assert.ok(is_same_day(pre(st_johns_dst_end), st_johns_dst_end, st_johns));
    assert.ok(is_same_day(pre(chatham_dst_begin), chatham_dst_begin, chatham));
    assert.ok(is_same_day(pre(chatham_dst_end), chatham_dst_end, chatham));
    assert.ok(!is_same_day(pre(kiritimati_date_skip), kiritimati_date_skip, kiritimati));
});

run_test("difference_in_calendar_days", () => {
    assert.equal(difference_in_calendar_days(pre(ny_new_year), ny_new_year, ny), -1);
    assert.equal(difference_in_calendar_days(pre(ny_new_year), ny_new_year_eve, ny), 0);
    assert.equal(difference_in_calendar_days(ny_new_year, ny_new_year_eve, ny), 1);
    assert.equal(difference_in_calendar_days(ny_new_year, pre(ny_new_year_eve), ny), 2);
    assert.equal(difference_in_calendar_days(st_johns_dst_end, st_johns_dst_begin, st_johns), 238);
    assert.equal(difference_in_calendar_days(chatham_dst_begin, chatham_dst_end, chatham), -189);

    // date-fns gives 2, but 1 seems more correct
    assert.equal(
        difference_in_calendar_days(kiritimati_date_skip, pre(kiritimati_date_skip), kiritimati),
        1,
    );
});
