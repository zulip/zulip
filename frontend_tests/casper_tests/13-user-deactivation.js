var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    var menu_selector = '#settings-dropdown';
    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
        casper.click('a[href^="#organization"]');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#settings_overlay_container.show', function () {
        casper.click("li[data-section='user-list-admin']");
    });
});

// Test user deactivation and reactivation
casper.then(function () {
    casper.waitUntilVisible('.user_row[data-email="cordelia@zulip.com"]', function () {
        casper.test.assertSelectorHasText('.user_row[data-email="cordelia@zulip.com"]', 'Deactivate');
        casper.click('.user_row[data-email="cordelia@zulip.com"] .deactivate');
        casper.test.assertTextExists('Deactivate cordelia@zulip.com', 'Deactivate modal has right user');
        casper.test.assertTextExists('Deactivate now', 'Deactivate now button available');
        casper.click('#do_deactivate_user_button');
    });
});

casper.then(function () {
    casper.waitUntilVisible('.user_row[data-email="cordelia@zulip.com"].deactivated_user', function () {
        casper.test.assertSelectorHasText('.user_row[data-email="cordelia@zulip.com"]', 'Reactivate');
        casper.click('.user_row[data-email="cordelia@zulip.com"] .reactivate');
    });
});

casper.then(function () {
    casper.waitUntilVisible('.user_row[data-email="cordelia@zulip.com"]:not(.deactivated_user)', function () {
        casper.test.assertSelectorHasText('.user_row[data-email="cordelia@zulip.com"]', 'Deactivate');
    });
});

casper.then(function () {
    // Test Deactivated users section of admin page
    casper.waitUntilVisible('.user_row[data-email="cordelia@zulip.com"]', function () {
        casper.test.assertSelectorHasText('.user_row[data-email="cordelia@zulip.com"]', 'Deactivate');
        casper.click('.user_row[data-email="cordelia@zulip.com"] .deactivate');
        casper.test.assertTextExists('Deactivate cordelia@zulip.com', 'Deactivate modal has right user');
        casper.test.assertTextExists('Deactivate now', 'Deactivate now button available');
        casper.click('#do_deactivate_user_button');
    });
});

casper.then(function () {
    // Leave the page and return
    casper.reload();

    casper.test.assertSelectorHasText("li[data-section='deactivated-users-admin']", "Deactivated users");
    casper.click("li[data-section='deactivated-users-admin']");


    casper.waitUntilVisible('#admin_deactivated_users_table .user_row[data-email="cordelia@zulip.com"] .reactivate', function () {
        casper.test.assertSelectorHasText('#admin_deactivated_users_table .user_row[data-email="cordelia@zulip.com"]', 'Reactivate');
        casper.click('#admin_deactivated_users_table .user_row[data-email="cordelia@zulip.com"] .reactivate');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin_deactivated_users_table .user_row[data-email="cordelia@zulip.com"] button:not(.reactivate)', function () {
        casper.test.assertSelectorHasText('#admin_deactivated_users_table .user_row[data-email="cordelia@zulip.com"]', 'Deactivate');
    });
});

// Test bot deactivation and reactivation
casper.then(function () {
    casper.test.assertSelectorHasText("li[data-section='organization-settings']", "Organization settings");
    casper.click("li[data-section='bot-list-admin']");
});

casper.then(function () {
    casper.waitUntilVisible('.user_row[data-email="new-user-bot@zulip.com"]', function () {
        casper.test.assertSelectorHasText('.user_row[data-email="new-user-bot@zulip.com"]', 'Deactivate');
        casper.click('.user_row[data-email="new-user-bot@zulip.com"] .deactivate');
    });
});

casper.then(function () {
    casper.waitUntilVisible('.user_row[data-email="new-user-bot@zulip.com"].deactivated_user', function () {
        casper.test.assertSelectorHasText('.user_row[data-email="new-user-bot@zulip.com"]', 'Reactivate');
        casper.click('.user_row[data-email="new-user-bot@zulip.com"] .reactivate');
    });
});

casper.then(function () {
    casper.waitUntilVisible('.user_row[data-email="new-user-bot@zulip.com"]:not(.deactivated_user)', function () {
        casper.test.assertSelectorHasText('.user_row[data-email="new-user-bot@zulip.com"]', 'Deactivate');
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
