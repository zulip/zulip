var common = require('../casper_lib/common.js').common;

// Test basic tab navigation.

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Testing navigation');
});

function wait_for_tab(tab) {
    casper.waitForSelector('#' + tab + '.tab-pane.active', function () {
        casper.test.assertExists('#' + tab + '.tab-pane.active', tab + ' page is active');
    });
}

function then_navigate_to(click_target, tab) {
    casper.then(function () {
        casper.test.info('Visiting #' + click_target);
        casper.click("a[href='#" + click_target + "']");
        wait_for_tab(tab);
    });
}

function then_navigate_to_settings() {
    casper.then(function () {
        casper.test.info('Navigate to settings');
        var menu_selector = '#settings-dropdown';
        casper.waitUntilVisible(menu_selector, function () {
            casper.click(menu_selector);
            casper.waitUntilVisible('a[href^="#settings"]', function () {
                casper.click('a[href^="#settings"]');
                casper.waitUntilVisible('#settings_page', function () {
                    casper.test.assertExists('#settings_page', "Settings page is active");
                    casper.click("#settings_page .exit");
                });
            });
        });
    });
}

function then_navigate_to_subscriptions() {
    casper.then(function () {
        casper.test.info('Navigate to subscriptions');

        var menu_selector = '#settings-dropdown';
        casper.waitUntilVisible(menu_selector, function () {
            casper.click(menu_selector);
            casper.click('a[href^="#streams"]');
            casper.waitUntilVisible("#subscription_overlay", function () {
                casper.test.assertExists('#subscriptions_table', "#subscriptions page is active");
            });
        });
    });
}

// Take a navigation tour of the app.
// Entries are (click target, tab that should be active after clicking).
then_navigate_to_settings();
then_navigate_to('narrow/stream/Verona', 'home');
then_navigate_to('home', 'home');
then_navigate_to_subscriptions();
then_navigate_to('', 'home');
then_navigate_to_settings();
then_navigate_to('narrow/stream/Verona', 'home');
then_navigate_to_subscriptions();
then_navigate_to('narrow/is/private', 'home');

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
