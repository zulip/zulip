var jsdom = require("jsdom");
var window = jsdom.jsdom().defaultView;
global.$ = require('jquery')(window);

add_dependencies({
    i18n: 'i18next',
    XDate: 'node_modules/xdate/src/xdate.js',
});

var timerender = require('js/timerender.js');

(function test_render_now_returns_today() {
    var today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    var expected = {
        time_str: i18n.t('Today'),
        formal_time_str: 'Friday, April 12, 2019',
        needs_update: true,
    };
    var actual = timerender.render_now(today, today);
    assert.equal(expected.time_str, actual.time_str);
    assert.equal(expected.formal_time_str, actual.formal_time_str);
    assert.equal(expected.needs_update, actual.needs_update);
}());

(function test_render_now_returns_yesterday() {
    var today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    var yesterday = today.clone().addDays(-1);
    var expected = {
        time_str: i18n.t('Yesterday'),
        formal_time_str: 'Thursday, April 11, 2019',
        needs_update: true,
    };
    var actual = timerender.render_now(yesterday, today);
    assert.equal(expected.time_str, actual.time_str);
    assert.equal(expected.formal_time_str, actual.formal_time_str);
    assert.equal(expected.needs_update, actual.needs_update);
}());

(function test_render_now_returns_year() {
    var today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    var year_ago = today.clone().addYears(-1);
    var expected = {
        time_str: 'Apr 12, 2018',
        formal_time_str: 'Thursday, April 12, 2018',
        needs_update: false,
    };
    var actual = timerender.render_now(year_ago, today);
    assert.equal(expected.time_str, actual.time_str);
    assert.equal(expected.formal_time_str, actual.formal_time_str);
    assert.equal(expected.needs_update, actual.needs_update);
}());

(function test_render_now_returns_month_and_day() {
    var today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    var three_months_ago = today.clone().addMonths(-3, true);
    var expected = {
        time_str: 'Jan 12',
        formal_time_str: 'Saturday, January 12, 2019',
        needs_update: false,
    };
    var actual = timerender.render_now(three_months_ago, today);
    assert.equal(expected.time_str, actual.time_str);
    assert.equal(expected.formal_time_str, actual.formal_time_str);
    assert.equal(expected.needs_update, actual.needs_update);
}());

(function test_render_now_returns_year_with_year_boundary() {
    var today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    var three_months_ago = today.clone().addMonths(-6, true);
    var expected = {
        time_str: 'Oct 12, 2018',
        formal_time_str: 'Friday, October 12, 2018',
        needs_update: false,
    };
    var actual = timerender.render_now(three_months_ago, today);
    assert.equal(expected.time_str, actual.time_str);
    assert.equal(expected.formal_time_str, actual.formal_time_str);
    assert.equal(expected.needs_update, actual.needs_update);
}());

(function test_render_date_renders_time_html() {
    var today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    var message_time  = today.clone();
    var expected_html = 'Today';
    var actual = timerender.render_date(message_time, undefined, today);
    assert.equal(expected_html, actual.html());
}());

(function test_render_date_renders_time_above_html() {
    var today = new XDate(1555091573000); // Friday 4/12/2019 5:52:53 PM (UTC+0)
    var message_time = today.clone();
    var message_time_above = today.clone().addDays(-1);
    var expected = $('<div></div>');
    expected.append('<i class="date-direction icon-vector-caret-up"></i>');
    expected.append('Yesterday');
    expected.append('<hr class="date-line">');
    expected.append('<i class="date-direction icon-vector-caret-down"></i>');
    expected.append('Today');
    var actual = timerender.render_date(message_time, message_time_above, today);
    assert.equal(expected.html(), actual.html());
}());

(function test_get_full_time() {
    var timestamp = 1495091573; // 5/18/2017 7:12:53 AM (UTC+0)
    var expected = '5/18/2017 7:12:53 AM (UTC+0)';
    var actual = timerender.get_full_time(timestamp);
    assert.equal(expected, actual);
}());

(function test_absolute_time_12_hour() {
    set_global('page_params', {
        twenty_four_hour_time: false,
    });

    // timestamp with hour > 12
    var timestamp = 1555091573000; // 4/12/2019 5:52:53 PM (UTC+0)
    var expected = 'Apr 12, 05:52 PM';
    var actual = timerender.absolute_time(timestamp);
    assert.equal(expected, actual);

    // timestamp with hour < 12
    timestamp = 1495091573000; // 5/18/2017 7:12:53 AM (UTC+0)
    expected = 'May 18, 07:12 AM';
    actual = timerender.absolute_time(timestamp);
    assert.equal(expected, actual);
}());

(function test_absolute_time_24_hour() {
    set_global('page_params', {
        twenty_four_hour_time: true,
    });

    // timestamp with hour > 12
    var timestamp = 1555091573000; // 4/12/2019 17:52:53 (UTC+0)
    var expected = 'Apr 12, 17:52';
    var actual = timerender.absolute_time(timestamp);
    assert.equal(expected, actual);

    // timestamp with hour < 12
    timestamp = 1495091573000; // 5/18/2017 7:12:53 AM (UTC+0)
    expected = 'May 18, 07:12';
    actual = timerender.absolute_time(timestamp);
    assert.equal(expected, actual);
}());

(function test_set_full_datetime() {
    var message = {
        timestamp: 1495091573, // 5/18/2017 7:12:53 AM (UTC+0)
    };
    var time_element = $('<span/>');
    var expected = '5/18/2017 7:12:53 AM (UTC+0)';
    timerender.set_full_datetime(message, time_element);
    var actual = time_element.attr('title');
    assert.equal(expected, actual);
}());
