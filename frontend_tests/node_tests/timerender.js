"use strict";

const {strict: assert} = require("assert");

const {add} = require("date-fns");
const MockDate = require("mockdate");

const {$t} = require("../zjsunit/i18n");
const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {user_settings} = require("../zjsunit/zpage_params");

user_settings.twenty_four_hour_time = true;

const timerender = zrequire("timerender");

run_test("get_tz_with_UTC_offset", () => {
    let time = new Date(1555091573000); // 4/12/2019 5:52:53 PM (UTC+0)
    assert.equal(timerender.get_tz_with_UTC_offset(time), "UTC");

    const previous_env_tz = process.env.TZ;

    // Test the GMT[+-]x:y logic.
    process.env.TZ = "Asia/Kolkata";
    assert.equal(timerender.get_tz_with_UTC_offset(time), "(UTC+05:30)");

    process.env.TZ = "America/Los_Angeles";
    assert.equal(timerender.get_tz_with_UTC_offset(time), "PDT (UTC-07:00)");

    time = new Date(1741003800000); // 3/3/2025 12:10:00 PM (UTC+0)
    assert.equal(timerender.get_tz_with_UTC_offset(time), "PST (UTC-08:00)");

    process.env.TZ = previous_env_tz;
});

run_test("render_now_returns_today", () => {
    const today = new Date(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const expected = {
        time_str: $t({defaultMessage: "Today"}),
        formal_time_str: "Friday, April 12, 2019",
        needs_update: true,
    };
    const actual = timerender.render_now(today, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_now_returns_yesterday", () => {
    const today = new Date(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const yesterday = add(today, {days: -1});
    const expected = {
        time_str: $t({defaultMessage: "Yesterday"}),
        formal_time_str: "Thursday, April 11, 2019",
        needs_update: true,
    };
    const actual = timerender.render_now(yesterday, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_now_returns_year", () => {
    const today = new Date(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const year_ago = add(today, {years: -1});
    const expected = {
        time_str: "Apr 12, 2018",
        formal_time_str: "Thursday, April 12, 2018",
        needs_update: false,
    };
    const actual = timerender.render_now(year_ago, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_now_returns_month_and_day", () => {
    const today = new Date(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const three_months_ago = add(today, {months: -3});
    const expected = {
        time_str: "Jan 12",
        formal_time_str: "Saturday, January 12, 2019",
        needs_update: false,
    };
    const actual = timerender.render_now(three_months_ago, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_now_returns_year_with_year_boundary", () => {
    const today = new Date(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const six_months_ago = add(today, {months: -6});
    const expected = {
        time_str: "Oct 12, 2018",
        formal_time_str: "Friday, October 12, 2018",
        needs_update: false,
    };
    const actual = timerender.render_now(six_months_ago, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_date_renders_time_html", () => {
    timerender.clear_for_testing();

    const today = new Date(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const message_time = today;
    const expected_html = $t({defaultMessage: "Today"});

    const attrs = {};
    const span_stub = $("<span />");

    span_stub.attr = (name, val) => {
        attrs[name] = val;
        return span_stub;
    };

    span_stub.append = (str) => {
        span_stub.html(str);
        return span_stub;
    };

    const actual = timerender.render_date(message_time, undefined, today);
    assert.equal(actual.html(), expected_html);
    assert.equal(attrs["data-tippy-content"], "Friday, April 12, 2019");
    assert.equal(attrs.class, "timerender0");
});

run_test("render_date_renders_time_above_html", () => {
    const today = new Date(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const message_time = today;
    const message_time_above = add(today, {days: -1});

    const span_stub = $("<span />");

    let appended_val;
    span_stub.append = (...val) => {
        appended_val = val;
        return span_stub;
    };

    const expected = [
        '<i class="date-direction fa fa-caret-up"></i>',
        $t({defaultMessage: "Yesterday"}),
        '<hr class="date-line">',
        '<i class="date-direction fa fa-caret-down"></i>',
        $t({defaultMessage: "Today"}),
    ];

    timerender.render_date(message_time, message_time_above, today);
    assert.deepEqual(appended_val, expected);
});

run_test("get_full_time", () => {
    const timestamp = 1495091573; // 5/18/2017 7:12:53 AM (UTC+0)
    const expected = "2017-05-18T07:12:53Z"; // ISO 8601 date format
    const actual = timerender.get_full_time(timestamp);
    assert.equal(actual, expected);
});

run_test("get_timestamp_for_flatpickr", () => {
    const unix_timestamp = 1495091573000; // 5/18/2017 7:12:53 AM (UTC+0)
    const iso_timestamp = "2017-05-18T07:12:53Z"; // ISO 8601 date format
    const func = timerender.get_timestamp_for_flatpickr;
    // Freeze time for testing.
    MockDate.set(new Date("2020-07-07T10:00:00Z").getTime());

    // Invalid timestamps should show current time.
    assert.equal(func("random str").valueOf(), Date.now());

    // Valid ISO timestamps should return Date objects.
    assert.equal(func(iso_timestamp).valueOf(), new Date(unix_timestamp).getTime());

    // Restore the Date object.
    MockDate.reset();
});

run_test("absolute_time_12_hour", () => {
    user_settings.twenty_four_hour_time = false;

    // timestamp with hour > 12, same year
    let timestamp = 1555091573000; // 4/12/2019 5:52:53 PM (UTC+0)
    let today = new Date(timestamp);
    let expected = "Apr 12 05:52 PM";
    let actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);

    // timestamp with hour > 12, different year
    today.setFullYear(today.getFullYear() + 1);
    expected = "Apr 12, 2019 05:52 PM";
    actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);

    // timestamp with hour < 12, same year
    timestamp = 1495091573000; // 5/18/2017 7:12:53 AM (UTC+0)
    today = new Date(timestamp);
    expected = "May 18 07:12 AM";
    actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);

    // timestamp with hour < 12, different year
    today.setFullYear(today.getFullYear() + 1);
    expected = "May 18, 2017 07:12 AM";
    actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);
});

run_test("absolute_time_24_hour", () => {
    user_settings.twenty_four_hour_time = true;

    // timestamp with hour > 12, same year
    let timestamp = 1555091573000; // 4/12/2019 5:52:53 PM (UTC+0)
    let today = new Date(timestamp);
    let expected = "Apr 12 17:52";
    let actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);

    // timestamp with hour > 12, different year
    today.setFullYear(today.getFullYear() + 1);
    expected = "Apr 12, 2019 17:52";
    actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);

    // timestamp with hour < 12, same year
    timestamp = 1495091573000; // 5/18/2017 7:12:53 AM (UTC+0)
    today = new Date(timestamp);
    expected = "May 18 07:12";
    actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);

    // timestamp with hour < 12, different year
    today.setFullYear(today.getFullYear() + 1);
    expected = "May 18, 2017 07:12";
    actual = timerender.absolute_time(timestamp, today);
    assert.equal(actual, expected);
});

run_test("get_full_datetime", () => {
    const time = new Date(1495141973000); // 2017/5/18 9:12:53 PM (UTC+0)
    let expected = "translated: 5/18/2017 at 9:12:53 PM UTC";
    assert.equal(timerender.get_full_datetime(time), expected);

    // test 24 hour time setting.
    user_settings.twenty_four_hour_time = true;
    expected = "translated: 5/18/2017 at 21:12:53 UTC";
    assert.equal(timerender.get_full_datetime(time), expected);

    user_settings.twenty_four_hour_time = false;

    // Test the GMT[+-]x:y logic.
    const previous_env_tz = process.env.TZ;
    process.env.TZ = "Asia/Kolkata";
    expected = "translated: 5/19/2017 at 2:42:53 AM (UTC+05:30)";
    assert.equal(timerender.get_full_datetime(time), expected);
    process.env.TZ = previous_env_tz;
});

run_test("last_seen_status_from_date", () => {
    // Set base_date to March 1 2016 12.30 AM (months are zero based)
    let base_date = new Date(2016, 2, 1, 0, 30);

    function assert_same(duration, expected_status) {
        const past_date = add(base_date, duration);
        const actual_status = timerender.last_seen_status_from_date(past_date, base_date);
        assert.equal(actual_status, expected_status);
    }

    assert_same({seconds: -20}, $t({defaultMessage: "Just now"}));

    assert_same({minutes: -1}, $t({defaultMessage: "Just now"}));

    assert_same({minutes: -2}, $t({defaultMessage: "Just now"}));

    assert_same({minutes: -30}, $t({defaultMessage: "30 minutes ago"}));

    assert_same({hours: -1}, $t({defaultMessage: "An hour ago"}));

    assert_same({hours: -2}, $t({defaultMessage: "2 hours ago"}));

    assert_same({hours: -20}, $t({defaultMessage: "20 hours ago"}));

    assert_same({hours: -24}, $t({defaultMessage: "Yesterday"}));

    assert_same({hours: -48}, $t({defaultMessage: "2 days ago"}));

    assert_same({days: -2}, $t({defaultMessage: "2 days ago"}));

    assert_same({days: -61}, $t({defaultMessage: "61 days ago"}));

    assert_same({days: -300}, $t({defaultMessage: "May 06,\u00A02015"}));

    assert_same({days: -366}, $t({defaultMessage: "Mar 01,\u00A02015"}));

    assert_same({years: -3}, $t({defaultMessage: "Mar 01,\u00A02013"}));

    // Set base_date to May 1 2016 12.30 AM (months are zero based)
    base_date = new Date(2016, 4, 1, 0, 30);

    assert_same({days: -91}, $t({defaultMessage: "Jan\u00A031"}));

    // Set base_date to May 1 2016 10.30 PM (months are zero based)
    base_date = new Date(2016, 4, 2, 23, 30);

    assert_same({hours: -1}, $t({defaultMessage: "An hour ago"}));

    assert_same({hours: -2}, $t({defaultMessage: "2 hours ago"}));

    assert_same({hours: -12}, $t({defaultMessage: "12 hours ago"}));

    assert_same({hours: -24}, $t({defaultMessage: "Yesterday"}));
});

run_test("set_full_datetime", () => {
    let time = new Date(1549958107000); // Tuesday 2/12/2019 07:55:07 AM (UTC+0)

    user_settings.twenty_four_hour_time = true;
    let time_str = timerender.stringify_time(time);
    let expected = "07:55";
    assert.equal(time_str, expected);

    user_settings.twenty_four_hour_time = false;
    time_str = timerender.stringify_time(time);
    expected = "7:55 AM";
    assert.equal(time_str, expected);

    time = new Date(1549979707000); // Tuesday 2/12/2019 13:55:07 PM (UTC+0)
    user_settings.twenty_four_hour_time = false;
    time_str = timerender.stringify_time(time);
    expected = "1:55 PM";
    assert.equal(time_str, expected);
});
