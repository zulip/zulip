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
                    casper.click('#settings_page .exit');
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
                casper.click('#subscription_overlay .exit');
            });
        });
    });
}

// Take a navigation tour of the app.
// Entries are (click target, tab that should be active after clicking).
then_navigate_to_settings();

var verona_narrow;
casper.then(function () {
    var verona_id = casper.evaluate(function () {
        return stream_data.get_stream_id('Verona');
    });
    verona_narrow = 'narrow/stream/' + verona_id + '-Verona';
    casper.test.info(verona_narrow);

    then_navigate_to(verona_narrow, 'home');
    then_navigate_to('home', 'home');
    then_navigate_to_subscriptions();
    then_navigate_to('', 'home');
    then_navigate_to_settings();
    then_navigate_to('narrow/is/private', 'home');
    then_navigate_to_subscriptions();
    then_navigate_to(verona_narrow, 'home');
});

var initial_page_load_time;
var hash;
var orig_hash;

// Verify reload.js's server-initiated browser reload hash
// save/restore logic works.
casper.then(function () {
    initial_page_load_time = casper.evaluate(function () {
        return page_params.page_load_time;
    });
    casper.test.info(initial_page_load_time);
    orig_hash = casper.evaluate(function () {
        return window.location.hash;
    });
    casper.evaluate(function () {
        reload.initiate({immediate: true});
    });
});

casper.then(function () {
    // Confirm that's we've actually reloaded using the page load timestamp.
    casper.waitFor(function () {
        return casper.evaluate(function (input) {
            return page_params.page_load_time > input;
        }, initial_page_load_time);
    }, function () {
        // Verify the hash was preserved
        hash = casper.evaluate(function () {
            return window.location.hash;
        });
    });
});

casper.then(function () {
    casper.waitUntilVisible('#zfilt', function () {
        // Verify that we're narrowed to the target stream
        casper.test.assertEquals(orig_hash, hash);
        casper.test.assertVisible("#zfilt");
        casper.test.assertNotVisible("#zhome");
    });
});

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
