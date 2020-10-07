"use strict";

const moment = require("moment");
const XDate = require("xdate");

set_global("$", global.make_zjquery());
set_global("page_params", {
    twenty_four_hour_time: true,
});

zrequire("timerender");

run_test("render_now_returns_today", () => {
    const today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const expected = {
        time_str: i18n.t("Today"),
        formal_time_str: "Friday, April 12, 2019",
        needs_update: true,
    };
    const actual = timerender.render_now(today, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_now_returns_yesterday", () => {
    const today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const yesterday = today.clone().addDays(-1);
    const expected = {
        time_str: i18n.t("Yesterday"),
        formal_time_str: "Thursday, April 11, 2019",
        needs_update: true,
    };
    const actual = timerender.render_now(yesterday, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_now_returns_year", () => {
    const today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const year_ago = today.clone().addYears(-1);
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
    const today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const three_months_ago = today.clone().addMonths(-3, true);
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
    const today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const three_months_ago = today.clone().addMonths(-6, true);
    const expected = {
        time_str: "Oct 12, 2018",
        formal_time_str: "Friday, October 12, 2018",
        needs_update: false,
    };
    const actual = timerender.render_now(three_months_ago, today);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);
});

run_test("render_date_renders_time_html", () => {
    const today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const message_time = today.clone();
    const expected_html = i18n.t("Today");

    const attrs = {};
    const span_stub = $("<span />");

    span_stub.attr = function (name, val) {
        attrs[name] = val;
        return span_stub;
    };

    span_stub.append = function (str) {
        span_stub.html(str);
        return span_stub;
    };

    const actual = timerender.render_date(message_time, undefined, today);
    assert.equal(actual.html(), expected_html);
    assert.equal(attrs.title, "Friday, April 12, 2019");
    assert.equal(attrs.class, "timerender0");
});

run_test("render_date_renders_time_above_html", () => {
    const today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    const message_time = today.clone();
    const message_time_above = today.clone().addDays(-1);

    const span_stub = $("<span />");

    let appended_val;
    span_stub.append = function (val) {
        appended_val = val;
        return span_stub;
    };

    const expected = [
        '<i class="date-direction fa fa-caret-up"></i>',
        i18n.t("Yesterday"),
        '<hr class="date-line">',
        '<i class="date-direction fa fa-caret-down"></i>',
        i18n.t("Today"),
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
    const date_now = Date.now;
    Date.now = () => new Date("2020-07-07T10:00:00Z").getTime();

    // Invalid timestamps should show current time.
    assert.equal(func("random str").valueOf(), moment().valueOf());

    // Valid ISO timestamps should return Date objects.
    assert.equal(func(iso_timestamp).valueOf(), moment(unix_timestamp).valueOf());

    // Restore the Date object.
    Date.now = date_now;
});

run_test("absolute_time_12_hour", () => {
    set_global("page_params", {
        twenty_four_hour_time: false,
    });

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
    set_global("page_params", {
        twenty_four_hour_time: true,
    });

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

run_test("set_full_datetime", () => {
    const message = {
        timestamp: 1495091573, // 2017/5/18 7:12:53 AM (UTC+0)
    };
    const time_element = $("<span/>");
    const attrs = {};

    time_element.attr = function (name, val) {
        attrs[name] = val;
        return time_element;
    };

    // The formatting of the string time.toLocale(Date|Time)String() on Node
    // might differ from the browser.
    const time = new Date(message.timestamp * 1000);
    const expected = `${time.toLocaleDateString()} 7:12:53 AM (UTC+0)`;
    timerender.set_full_datetime(message, time_element);
    assert.equal(attrs.title, expected);
});

run_test("last_seen_status_from_date", () => {
    // Set base_dateto to March 1 2016 12.30 AM (months are zero based)
    let base_date = new XDate(2016, 2, 1, 0, 30);

    function assert_same(modifier, expected_status) {
        let past_date = base_date.clone();
        past_date = modifier(past_date);
        const actual_status = timerender.last_seen_status_from_date(past_date, base_date);
        assert.equal(actual_status, expected_status);
    }

    assert_same((d) => d.addSeconds(-20), i18n.t("Just now"));

    assert_same((d) => d.addMinutes(-1), i18n.t("Just now"));

    assert_same((d) => d.addMinutes(-2), i18n.t("Just now"));

    assert_same((d) => d.addMinutes(-30), i18n.t("30 minutes ago"));

    assert_same((d) => d.addHours(-1), i18n.t("An hour ago"));

    assert_same((d) => d.addHours(-2), i18n.t("2 hours ago"));

    assert_same((d) => d.addHours(-20), i18n.t("20 hours ago"));

    assert_same((d) => d.addDays(-1), i18n.t("Yesterday"));

    assert_same((d) => d.addDays(-2), i18n.t("2 days ago"));

    assert_same((d) => d.addDays(-61), i18n.t("61 days ago"));

    assert_same((d) => d.addDays(-300), i18n.t("May 06,\u00A02015"));

    assert_same((d) => d.addDays(-366), i18n.t("Mar 01,\u00A02015"));

    assert_same((d) => d.addYears(-3), i18n.t("Mar 01,\u00A02013"));

    // Set base_dateto to May 1 2016 12.30 AM (months are zero based)
    base_date = new XDate(2016, 4, 1, 0, 30);

    assert_same((d) => d.addDays(-91), i18n.t("Jan\u00A031"));
});

run_test("set_full_datetime", () => {
    let time = new XDate(1549958107000); // Tuesday 2/12/2019 07:55:07 AM (UTC+0)
    let time_str = timerender.stringify_time(time);
    let expected = "07:55";
    assert.equal(time_str, expected);

    page_params.twenty_four_hour_time = false;
    time_str = timerender.stringify_time(time);
    expected = "7:55 AM";
    assert.equal(time_str, expected);

    time = new XDate(1549979707000); // Tuesday 2/12/2019 13:55:07 PM (UTC+0)
    page_params.twenty_four_hour_time = false;
    time_str = timerender.stringify_time(time);
    expected = "1:55 PM";
    assert.equal(time_str, expected);
});
