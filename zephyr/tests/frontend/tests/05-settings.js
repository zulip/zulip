var common = require('../common.js').common;

common.start_and_log_in();

var form_sel = 'form[action^="/json/settings/change"]';

casper.then(function() {
    casper.test.info('Settings page');
    casper.click('a[href^="#settings"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#settings/, 'URL suggests we are on settings page');
    casper.test.assertExists('#settings.tab-pane.active', 'Settings page is active');

    casper.test.assertNotVisible("#old_password");
    casper.test.assertSelectorHasText('.my_fullname', 'Iago');

    casper.click(".change_password_button");
});

casper.waitUntilVisible("#old_password", function() {
    casper.test.assertVisible("#old_password");
    casper.test.assertVisible("#new_password");
    casper.test.assertVisible("#confirm_password");

    casper.test.assertEqual(casper.getFormValues(form_sel).full_name, "Iago");

    casper.fill(form_sel, {
        "full_name": "IagoNew",
        "old_password": "FlokrWdZefyEWkfI",
        "new_password": "qwertyuiop",
        "confirm_password": "qwertyuiop"
    });
    casper.click('input[name="change_settings"]');
});

casper.waitUntilVisible('#settings-status', function () {
    casper.test.assertSelectorHasText('#settings-status', 'Updated settings!');
    casper.test.assertSelectorHasText('.my_fullname', 'IagoNew');

    casper.test.assertNotVisible('');
    casper.click('#api_key_button');
});

casper.waitUntilVisible('#get_api_key_password', function () {
    casper.fill('form[action^="/json/fetch_api_key"]', {'password':'qwertyuiop'});
    casper.click('input[name="view_api_key"]');
});

casper.waitUntilVisible('#api_key_value', function () {
    casper.test.assertMatch(casper.fetchText('#api_key_value'), /[a-zA-Z0-9]{32}/, "Looks like an API key");

    // Change it all back so the next test can still log in
    casper.fill(form_sel, {
        "full_name": "Iago",
        "old_password": "qwertyuiop",
        "new_password": "FlokrWdZefyEWkfI",
        "confirm_password": "FlokrWdZefyEWkfI"
    });
    casper.click('input[name="change_settings"]');
});

casper.waitUntilVisible('#settings-status', function () {
    casper.test.assertSelectorHasText('#settings-status', 'Updated settings!');
});

// TODO: test the "Declare Humbug Bankruptcy option"

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
