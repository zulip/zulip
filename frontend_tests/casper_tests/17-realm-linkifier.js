var common = require('../casper_lib/common.js');

common.start_and_log_in();

common.manage_organization();

// Test custom realm filters
casper.then(function () {
    casper.click("li[data-section='filter-settings']");
    casper.waitUntilVisible('.admin-filter-form', function () {
        casper.fill('form.admin-filter-form', {
            pattern: '#(?P<id>[0-9]+)',
            url_format_string: 'https://trac.example.com/ticket/%(id)s',
        });
        casper.click('form.admin-filter-form button.button');
    });
});

casper.then(function () {
    casper.waitUntilVisible('div#admin-filter-status', function () {
        casper.test.assertSelectorHasText('div#admin-filter-status', 'Custom filter added!');
    });
});

casper.then(function () {
    casper.waitUntilVisible('.filter_row', function () {
        casper.test.assertSelectorHasText('.filter_row span.filter_pattern', '#(?P<id>[0-9]+)');
        casper.test.assertSelectorHasText('.filter_row span.filter_url_format_string', 'https://trac.example.com/ticket/%(id)s');
        casper.click('.filter_row button');
    });
});

casper.then(function () {
    casper.waitWhileVisible('.filter_row', function () {
        casper.test.assertDoesntExist('.filter_row');
    });
});

casper.then(function () {
    casper.waitUntilVisible('.admin-filter-form', function () {
        casper.fill('form.admin-filter-form', {
            pattern: 'a$',
            url_format_string: 'https://trac.example.com/ticket/%(id)s',
        });
        casper.click('form.admin-filter-form button.button');
    });
});

casper.then(function () {
    casper.waitUntilVisible('div#admin-filter-pattern-status', function () {
        casper.test.assertSelectorHasText('div#admin-filter-pattern-status', 'Failed: Invalid filter pattern');
    });
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
