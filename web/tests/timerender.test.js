"use strict";

const {strict: assert} = require("assert");

const {add} = require("date-fns");
const MockDate = require("mockdate");

const {$t} = require("./lib/i18n");
const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {user_settings} = require("./lib/zpage_params");

user_settings.twenty_four_hour_time = true;

const timerender = zrequire("timerender");

function get_date(time_ISO, DOW) {
    const time = new Date(time_ISO);
    // DOW helps the test reader to know the DOW of the current date being tested.
    assert.equal(new Intl.DateTimeFormat("en-US", {weekday: "long"}).format(time), DOW);
    return time;
}

const date_2017 = get_date("2017-05-18T07:12:53.000Z", "Thursday");

// Check there is no UTC offset.
assert.equal(timerender.get_tz_with_UTC_offset(date_2017.getTime()), "UTC");

const date_2017_PM = get_date("2017-05-18T21:12:53.000Z", "Thursday");

const date_2019 = get_date("2019-04-12T17:52:53.000Z", "Friday");

const date_2021 = get_date("2021-01-27T01:53:08.000Z", "Wednesday");

const date_2025 = get_date("2025-03-03T12:10:00.000Z", "Monday");

run_test("get_localized_date_or_time_for_format returns default date with incorrect locale", () => {
    const date = date_2019;
    const expectedDate = "Friday, April 12, 2019";

    user_settings.default_language = "invalid";
    const actualDate = timerender.get_localized_date_or_time_for_format(
        date,
        "weekday_dayofyear_year",
    );

    assert.equal(actualDate, expectedDate);
});

run_test("get_localized_date_or_time_for_format returns correct format", () => {
    const date = date_2021;
    const formats = [
        {
            format: "time",
            expected: {
                date: "1:53 AM",
            },
        },
        {
            format: "time_sec",
            expected: {
                date: "1:53:08 AM",
            },
        },
        {
            format: "weekday",
            expected: {
                date: "Wednesday",
            },
        },
        {
            format: "dayofyear",
            expected: {
                date: "Jan 27",
            },
        },
        {
            format: "dayofyear_time",
            expected: {
                date: "Jan 27, 1:53 AM",
            },
        },
        {
            format: "dayofyear_year",
            expected: {
                date: "Jan 27, 2021",
            },
        },
        {
            format: "dayofyear_year_time",
            expected: {
                date: "Jan 27, 2021, 1:53 AM",
            },
        },
        {
            format: "weekday_dayofyear_year",
            expected: {
                date: "Wednesday, January 27, 2021",
            },
        },
        {
            format: "weekday_dayofyear_year_time",
            expected: {
                date: "Wed, Jan 27, 2021, 1:53 AM",
            },
        },
        {
            format: "full_weekday_dayofyear_year_time",
            expected: {
                date: "Wednesday, January 27, 2021 at 1:53 AM",
            },
        },
    ];

    for (const format of formats) {
        const actualDate = timerender.get_localized_date_or_time_for_format(date, format.format);
        assert.equal(actualDate, format.expected.date);
    }
});

run_test("get_localized_date_or_time_for_format returns correct localized date", () => {
    const date = add(date_2019, {years: -1});
    const languages = [
        {
            language: "en",
            expected: {
                date: "Thursday, April 12, 2018",
            },
        },
        {
            language: "ru",
            expected: {
                date: "четверг, 12 апреля 2018 г.",
            },
        },
        {
            language: "fr",
            expected: {
                date: "jeudi 12 avril 2018",
            },
        },
        {
            language: "de",
            expected: {
                date: "Donnerstag, 12. April 2018",
            },
        },
        {
            language: "su",
            expected: {
                date: "Kemis, 12 April 2018",
            },
        },
        {
            language: "it",
            expected: {
                date: "giovedì 12 aprile 2018",
            },
        },
    ];

    for (const language of languages) {
        user_settings.default_language = language.language;
        const actualDate = timerender.get_localized_date_or_time_for_format(
            date,
            "weekday_dayofyear_year",
        );
        assert.equal(actualDate, language.expected.date);
    }
});

run_test("get_tz_with_UTC_offset", () => {
    let time = date_2019;

    assert.equal(timerender.get_tz_with_UTC_offset(time), "UTC");

    // Test the GMT[+-]x:y logic.
    timerender.set_display_time_zone("Asia/Kolkata");
    assert.equal(timerender.get_tz_with_UTC_offset(time), "(UTC+05:30)");

    timerender.set_display_time_zone("America/Los_Angeles");
    assert.equal(timerender.get_tz_with_UTC_offset(time), "PDT (UTC-07:00)");

    time = date_2025;

    assert.equal(timerender.get_tz_with_UTC_offset(time), "PST (UTC-08:00)");

    timerender.set_display_time_zone("UTC");
});

run_test("render_now_returns_today", () => {
    MockDate.set(date_2019.getTime());

    const expected = {
        time_str: $t({defaultMessage: "Today"}),
        formal_time_str: "Friday, April 12, 2019",
        needs_update: true,
    };
    const actual = timerender.render_now(date_2019);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);

    MockDate.reset();
});

run_test("render_now_returns_yesterday", () => {
    MockDate.set(date_2019.getTime());

    const yesterday = add(date_2019, {days: -1});
    const expected = {
        time_str: $t({defaultMessage: "Yesterday"}),
        formal_time_str: "Thursday, April 11, 2019",
        needs_update: true,
    };
    const actual = timerender.render_now(yesterday);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);

    MockDate.reset();
});

run_test("render_now_returns_year", () => {
    MockDate.set(date_2019.getTime());

    const year_ago = add(date_2019, {years: -1});
    const expected = {
        time_str: "Apr 12, 2018",
        formal_time_str: "Thursday, April 12, 2018",
        needs_update: false,
    };
    const actual = timerender.render_now(year_ago);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);

    MockDate.reset();
});

run_test("render_now_returns_month_and_day", () => {
    MockDate.set(date_2019.getTime());

    const three_months_ago = add(date_2019, {months: -3});
    const expected = {
        time_str: "Jan 12",
        formal_time_str: "Saturday, January 12, 2019",
        needs_update: false,
    };
    const actual = timerender.render_now(three_months_ago);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);

    MockDate.reset();
});

run_test("format_time_modern", () => {
    const today = date_2021;

    const few_minutes_in_future = add(today, {minutes: 30});
    const weeks_in_future = add(today, {days: 20});
    const less_than_24_hours_ago = add(today, {hours: -23});
    const twenty_four_hours_ago = add(today, {hours: -24});
    const more_than_24_hours_ago = add(today, {hours: -25});
    const less_than_a_week_ago = add(today, {days: -6});
    const one_week_ago = add(today, {days: -7});
    const less_than_6_months_ago = add(today, {months: -3});
    const more_than_6_months_ago = add(today, {months: -9});
    const previous_year_but_less_than_6_months = add(today, {months: -1});

    assert.equal(timerender.format_time_modern(few_minutes_in_future, today), "Jan 27, 2021");
    assert.equal(timerender.format_time_modern(weeks_in_future, today), "Feb 16, 2021");
    assert.equal(timerender.format_time_modern(less_than_24_hours_ago, today), "2:53 AM");
    assert.equal(
        timerender.format_time_modern(twenty_four_hours_ago, today),
        "translated: Yesterday",
    );
    assert.equal(
        timerender.format_time_modern(more_than_24_hours_ago, today),
        "translated: Yesterday",
    );
    assert.equal(timerender.format_time_modern(less_than_a_week_ago, today), "Thursday");
    assert.equal(timerender.format_time_modern(one_week_ago, today), "Jan 20");
    assert.equal(
        timerender.format_time_modern(previous_year_but_less_than_6_months, today),
        "Dec 27",
    );
    assert.equal(timerender.format_time_modern(less_than_6_months_ago, today), "Oct 27");
    assert.equal(timerender.format_time_modern(more_than_6_months_ago, today), "Apr 27, 2020");
});

run_test("format_time_modern_different_timezones", () => {
    // Day is yesterday in UTC+0 but is 2 days ago in local timezone hence DOW is returned.
    let today = date_2017_PM;
    let yesterday = add(date_2017, {days: -1});
    assert.equal(timerender.format_time_modern(yesterday, today), "translated: Yesterday");

    timerender.set_display_time_zone("America/Juneau");
    let expected = "translated: 5/16/2017 at 11:12:53 PM AKDT (UTC-08:00)";
    assert.equal(timerender.get_full_datetime_clarification(yesterday), expected);
    assert.equal(timerender.format_time_modern(yesterday, today), "Tuesday");
    timerender.set_display_time_zone("UTC");

    // Day is 2 days ago in UTC+0 but is yesterday in local timezone.
    today = date_2017;
    yesterday = add(date_2017_PM, {days: -2});
    assert.equal(timerender.format_time_modern(yesterday, today), "Tuesday");

    timerender.set_display_time_zone("Asia/Brunei");
    expected = "translated: 5/17/2017 at 5:12:53 AM (UTC+08:00)";
    assert.equal(timerender.get_full_datetime_clarification(yesterday), expected);
    assert.equal(timerender.format_time_modern(yesterday, today), "translated: Yesterday");
    timerender.set_display_time_zone("UTC");

    // Day is 6 days ago in UTC+0 but a week ago in local timezone hence difference in returned strings.
    today = date_2017_PM;
    yesterday = add(date_2017, {days: -6});
    assert.equal(timerender.format_time_modern(yesterday, today), "Friday");

    timerender.set_display_time_zone("America/Juneau");
    expected = "translated: 5/11/2017 at 11:12:53 PM AKDT (UTC-08:00)";
    assert.equal(timerender.get_full_datetime_clarification(yesterday), expected);
    assert.equal(timerender.format_time_modern(yesterday, today), "May 11");
    timerender.set_display_time_zone("UTC");
});

run_test("render_now_returns_year_with_year_boundary", () => {
    MockDate.set(date_2019.getTime());

    const six_months_ago = add(date_2019, {months: -6});
    const expected = {
        time_str: "Oct 12, 2018",
        formal_time_str: "Friday, October 12, 2018",
        needs_update: false,
    };
    const actual = timerender.render_now(six_months_ago);
    assert.equal(actual.time_str, expected.time_str);
    assert.equal(actual.formal_time_str, expected.formal_time_str);
    assert.equal(actual.needs_update, expected.needs_update);

    MockDate.reset();
});

run_test("render_date_renders_time_html", () => {
    timerender.clear_for_testing();

    const today = date_2019;
    MockDate.set(today.getTime());

    const message_time = today;
    const expected_text = $t({defaultMessage: "Today"});

    const attrs = {};
    const $span_stub = $("<span>");

    $span_stub.attr = (name, val) => {
        attrs[name] = val;
        return $span_stub;
    };

    const $actual = timerender.render_date(message_time);
    assert.equal($actual.text(), expected_text);
    assert.equal(attrs["data-tippy-content"], "Friday, April 12, 2019");
    assert.equal(attrs.class, "timerender-content timerender0");

    MockDate.reset();
});

run_test("get_full_time", () => {
    const timestamp = date_2017.getTime() / 1000;
    const expected = "2017-05-18T07:12:53Z"; // ISO 8601 date format
    const actual = timerender.get_full_time(timestamp);
    assert.equal(actual, expected);
});

run_test("get_timestamp_for_flatpickr", () => {
    const func = timerender.get_timestamp_for_flatpickr;
    // Freeze time for testing.
    MockDate.set(date_2017.getTime());

    // Invalid timestamps should show current time on the hour.
    const date_without_minutes = new Date();
    date_without_minutes.setMinutes(0, 0);
    assert.equal(func("random str").valueOf(), date_without_minutes.getTime());

    // Valid ISO timestamps should return the timestamp.
    assert.equal(func(date_2017.toISOString()).valueOf(), date_2017.getTime());

    // Restore the Date object.
    MockDate.reset();
});

run_test("absolute_time_12_hour", () => {
    user_settings.twenty_four_hour_time = false;

    // timestamp with hour > 12, same year
    let timestamp = date_2019.getTime();

    let today = date_2019;
    MockDate.set(today.getTime());
    let expected = "Apr 12, 5:52 PM";
    let actual = timerender.absolute_time(timestamp);
    assert.equal(actual, expected);

    // timestamp with hour > 12, different year
    let next_year = add(today, {years: 1});
    MockDate.set(next_year.getTime());
    expected = "Apr 12, 2019, 5:52 PM";
    actual = timerender.absolute_time(timestamp);
    assert.equal(actual, expected);

    // timestamp with hour < 12, same year
    timestamp = date_2017.getTime();

    today = date_2017;
    MockDate.set(today.getTime());
    expected = "May 18, 7:12 AM";
    actual = timerender.absolute_time(timestamp);
    assert.equal(actual, expected);

    // timestamp with hour < 12, different year
    next_year = add(today, {years: 1});
    MockDate.set(next_year.getTime());
    expected = "May 18, 2017, 7:12 AM";
    actual = timerender.absolute_time(timestamp);
    assert.equal(actual, expected);

    MockDate.reset();
});

run_test("absolute_time_24_hour", () => {
    user_settings.twenty_four_hour_time = true;

    // date with hour > 12, same year
    let today = date_2019;
    MockDate.set(today.getTime());
    let expected = "Apr 12, 17:52";
    let actual = timerender.absolute_time(date_2019.getTime());
    assert.equal(actual, expected);

    // date with hour > 12, different year
    let next_year = add(today, {years: 1});
    MockDate.set(next_year.getTime());
    expected = "Apr 12, 2019, 17:52";
    actual = timerender.absolute_time(date_2019.getTime());
    assert.equal(actual, expected);

    // timestamp with hour < 12, same year
    today = date_2017;
    MockDate.set(today.getTime());
    expected = "May 18, 07:12";
    actual = timerender.absolute_time(date_2017.getTime());
    assert.equal(actual, expected);

    // timestamp with hour < 12, different year
    next_year = add(today, {years: 1});
    MockDate.set(next_year.getTime());
    expected = "May 18, 2017, 07:12";
    actual = timerender.absolute_time(date_2017.getTime());
    assert.equal(actual, expected);

    MockDate.reset();
});

run_test("get_full_datetime", () => {
    const time = date_2017_PM;

    let expected = "translated: 5/18/2017 at 9:12:53 PM UTC";
    assert.equal(timerender.get_full_datetime_clarification(time), expected);
    expected = "translated: May 18, 2017 at 9:12:53 PM";
    assert.equal(timerender.get_full_datetime(time), expected);

    expected = "translated: 5/18/2017 at 9:12 PM UTC";
    assert.equal(timerender.get_full_datetime_clarification(time, "time"), expected);
    expected = "translated: May 18, 2017 at 9:12 PM";
    assert.equal(timerender.get_full_datetime(time, "time"), expected);

    // test 24 hour time setting.
    user_settings.twenty_four_hour_time = true;
    expected = "translated: 5/18/2017 at 21:12:53 UTC";
    assert.equal(timerender.get_full_datetime_clarification(time), expected);
    expected = "translated: May 18, 2017 at 21:12:53";
    assert.equal(timerender.get_full_datetime(time), expected);

    user_settings.twenty_four_hour_time = false;

    // Test the GMT[+-]x:y logic.
    timerender.set_display_time_zone("Asia/Kolkata");
    expected = "translated: 5/19/2017 at 2:42:53 AM (UTC+05:30)";
    assert.equal(timerender.get_full_datetime_clarification(time), expected);
    expected = "translated: May 19, 2017 at 2:42:53 AM";
    assert.equal(timerender.get_full_datetime(time), expected);
    timerender.set_display_time_zone("UTC");
});

run_test("last_seen_status_from_date", () => {
    // Set base_date to March 1 2016 12.30 AM (months are zero based)
    let base_date = new Date(2016, 2, 1, 0, 30);
    MockDate.set(base_date.getTime());

    function assert_same(duration, expected_status) {
        const past_date = add(base_date, duration);
        const actual_status = timerender.last_seen_status_from_date(past_date, base_date);
        assert.equal(actual_status, expected_status);
    }

    assert_same({minutes: -30}, $t({defaultMessage: "Active 30 minutes ago"}));

    assert_same({hours: -1}, $t({defaultMessage: "Active an hour ago"}));

    assert_same({hours: -2}, $t({defaultMessage: "Active 2 hours ago"}));

    assert_same({hours: -20}, $t({defaultMessage: "Active 20 hours ago"}));

    assert_same({hours: -24}, $t({defaultMessage: "Active yesterday"}));

    assert_same({hours: -48}, $t({defaultMessage: "Active 2 days ago"}));

    assert_same({days: -2}, $t({defaultMessage: "Active 2 days ago"}));

    assert_same({days: -61}, $t({defaultMessage: "Active 61 days ago"}));

    assert_same({days: -300}, $t({defaultMessage: "Active May 6, 2015"}));

    assert_same({days: -366}, $t({defaultMessage: "Active Mar 1, 2015"}));

    assert_same({years: -3}, $t({defaultMessage: "Active Mar 1, 2013"}));

    // Set base_date to May 1 2016 12.30 AM (months are zero based)
    base_date = new Date(2016, 4, 1, 0, 30);
    MockDate.set(base_date.getTime());

    assert_same({days: -91}, $t({defaultMessage: "Active Jan 31"}));

    // Set base_date to May 1 2016 10.30 PM (months are zero based)
    base_date = new Date(2016, 4, 2, 23, 30);
    MockDate.set(base_date.getTime());

    assert_same({hours: -1}, $t({defaultMessage: "Active an hour ago"}));

    assert_same({hours: -2}, $t({defaultMessage: "Active 2 hours ago"}));

    assert_same({hours: -12}, $t({defaultMessage: "Active 12 hours ago"}));

    assert_same({hours: -24}, $t({defaultMessage: "Active yesterday"}));

    MockDate.reset();
});

run_test("relative_time_string_from_date", () => {
    // Set base_date to March 1 2016 12.30 AM (months are zero based)
    let base_date = new Date(2016, 2, 1, 0, 30);
    MockDate.set(base_date.getTime());

    function assert_same(duration, expected_status) {
        const past_date = add(base_date, duration);
        const actual_status = timerender.relative_time_string_from_date(past_date);
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

    assert_same({days: -300}, "May 6, 2015");

    assert_same({days: -366}, "Mar 1, 2015");

    assert_same({years: -3}, "Mar 1, 2013");

    // Set base_date to May 1 2016 12.30 AM (months are zero based)
    base_date = new Date(2016, 4, 1, 0, 30);
    MockDate.set(base_date.getTime());

    assert_same({days: -91}, "Jan 31");

    // Set base_date to May 1 2016 10.30 PM (months are zero based)
    base_date = new Date(2016, 4, 2, 23, 30);
    MockDate.set(base_date.getTime());

    assert_same({hours: -1}, $t({defaultMessage: "An hour ago"}));

    assert_same({hours: -2}, $t({defaultMessage: "2 hours ago"}));

    assert_same({hours: -12}, $t({defaultMessage: "12 hours ago"}));

    assert_same({hours: -24}, $t({defaultMessage: "Yesterday"}));

    MockDate.reset();
});

run_test("set_full_datetime", () => {
    let time = date_2019;

    user_settings.twenty_four_hour_time = true;
    let time_str = timerender.stringify_time(time);
    let expected = "17:52";
    assert.equal(time_str, expected);

    user_settings.twenty_four_hour_time = false;
    time_str = timerender.stringify_time(time);
    expected = "5:52 PM";
    assert.equal(time_str, expected);

    time = add(time, {hours: -7}); // time between 1 to 12 o'clock time.
    user_settings.twenty_four_hour_time = false;
    time_str = timerender.stringify_time(time);
    expected = "10:52 AM";
    assert.equal(time_str, expected);
});

run_test("should_display_profile_incomplete_alert", () => {
    // Organization created < 15 days ago
    let realm_date_created = new Date();
    realm_date_created.setDate(realm_date_created.getDate() - 5);

    assert.equal(timerender.should_display_profile_incomplete_alert(realm_date_created), false);

    // Organization created > 15 days ago
    realm_date_created = new Date();
    realm_date_created.setDate(realm_date_created.getDate() - 15);

    assert.equal(timerender.should_display_profile_incomplete_alert(realm_date_created), true);
});
