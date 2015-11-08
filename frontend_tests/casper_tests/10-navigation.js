var common = require('../casper_lib/common.js').common;

// Test basic tab navigation.

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Testing navigation');
});

function then_navigate_to(click_target, tab) {
    casper.then(function () {
        casper.test.info('Visiting #' + click_target);
        casper.click('a[href^="#' + click_target + '"]');
    });

    casper.waitForSelector('#' + tab + '.tab-pane.active', function () {
        casper.test.assertExists('#' + tab + '.tab-pane.active', tab + ' page is active');
    });
}

// Take a navigation tour of the app.
// Entries are (click target, tab that should be active after clicking).
var tabs = [["settings", "settings"], ["home", "home"],
            ["subscriptions", "subscriptions"], ["", "home"],
            ["settings", "settings"], ["narrow/stream/Verona", "home"],
            ["subscriptions", "subscriptions"], ["narrow/is/private", "home"]];
var i;

for (i=0; i<tabs.length; i++) {
    then_navigate_to(tabs[i][0], tabs[i][1]);
}

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
