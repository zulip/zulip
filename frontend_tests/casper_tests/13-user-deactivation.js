var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    var menu_selector = '#settings-dropdown';
    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
        casper.click('a[href^="#administration"]');
    });
});

// Test user deactivation and reactivation
casper.then(function () {
    casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"]', function () {
        casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
        casper.click('.user_row[id="user_cordelia@zulip.com"] .deactivate');
        casper.test.assertTextExists('Deactivate cordelia@zulip.com', 'Deactivate modal has right user');
        casper.test.assertTextExists('Deactivate now', 'Deactivate now button available');
        casper.click('#do_deactivate_user_button');
    });
});

casper.then(function () {
    casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"].deactivated_user', function () {
        casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Reactivate');
        casper.click('.user_row[id="user_cordelia@zulip.com"] .reactivate');
    });
});

casper.then(function () {
    casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"]:not(.deactivated_user)', function () {
        casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
    });
});

casper.then(function () {
    // Test Deactivated users section of admin page
    casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"]', function () {
        casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
        casper.click('.user_row[id="user_cordelia@zulip.com"] .deactivate');
        casper.test.assertTextExists('Deactivate cordelia@zulip.com', 'Deactivate modal has right user');
        casper.test.assertTextExists('Deactivate now', 'Deactivate now button available');
        casper.click('#do_deactivate_user_button');
    });
});

casper.then(function () {
    // Leave the page and return
    casper.click('#settings-dropdown');
    casper.click('a[href^="#"]');
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');

    casper.test.assertSelectorHasText("#administration a[aria-controls='deactivated-users']", "Deactivated users");
    casper.click("#administration a[aria-controls='deactivated-users']");


    casper.waitForSelector('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"] .reactivate', function () {
        casper.test.assertSelectorHasText('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"]', 'Reactivate');
        casper.click('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"] .reactivate');
    });
});

casper.then(function () {
    casper.waitForSelector('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"] button:not(.reactivate)', function () {
        casper.test.assertSelectorHasText('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
    });

    casper.test.assertSelectorHasText("#administration a[aria-controls='organization']", "Organization");
    casper.click("#administration a[aria-controls='organization']");
});

casper.then(function () {
    // Test bot deactivation and reactivation
    casper.waitForSelector('.user_row[id="user_new-user-bot@zulip.com"]', function () {
        casper.test.assertSelectorHasText('.user_row[id="user_new-user-bot@zulip.com"]', 'Deactivate');
        casper.click('.user_row[id="user_new-user-bot@zulip.com"] .deactivate');
    });
});

casper.then(function () {
    casper.waitForSelector('.user_row[id="user_new-user-bot@zulip.com"].deactivated_user', function () {
        casper.test.assertSelectorHasText('.user_row[id="user_new-user-bot@zulip.com"]', 'Reactivate');
        casper.click('.user_row[id="user_new-user-bot@zulip.com"] .reactivate');
    });
});

casper.then(function () {
    casper.waitForSelector('.user_row[id="user_new-user-bot@zulip.com"]:not(.deactivated_user)', function () {
        casper.test.assertSelectorHasText('.user_row[id="user_new-user-bot@zulip.com"]', 'Deactivate');
    });
});

// NOTE: Any additional test code adding to the bottom of this test
// suite has risk of being weirdly flaky; we don't know why, but we
// recommend just adding a new suite if needed, since there isn't much
// overhead.

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
