var common = require('../casper_lib/common.js').common;
var test_credentials = require('../../var/casper/test_credentials.js').test_credentials;
var REALMS_HAVE_SUBDOMAINS = casper.cli.get('subdomains');

common.start_and_log_in();

var form_sel = 'form[action^="/json/settings/change"]';
var regex_zuliprc = /^data:application\/octet-stream;charset=utf-8,\[api\]\nemail=.+\nkey=.+\nsite=.+\n$/;

casper.then(function () {
    var menu_selector = '#settings-dropdown';
    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
    });
});

casper.then(function () {
    casper.waitUntilVisible('a[href^="#settings"]', function () {
        casper.test.info('Settings page');
        casper.click('a[href^="#settings"]');
    });
});

casper.then(function () {
    casper.waitUntilVisible("#settings_content .account-settings-form", function () {
        casper.test.assertUrlMatch(/^http:\/\/[^/]+\/#settings/, 'URL suggests we are on settings page');
        casper.test.assertVisible('.account-settings-form', 'Settings page is active');

        casper.test.assertNotVisible("#pw_change_controls");

        casper.click(".change_password_button");
    });
});

casper.then(function () {
    casper.waitUntilVisible("#pw_change_controls", function () {
        casper.waitForResource("zxcvbn.js", function () {
            casper.test.assertVisible("#old_password");
            casper.test.assertVisible("#new_password");
            casper.test.assertVisible("#confirm_password");

            casper.test.assertEqual(casper.getFormValues(form_sel).full_name, "Iago");

            casper.fill(form_sel, {
                full_name: "IagoNew",
                old_password: test_credentials.default_user.password,
                new_password: "qwertyuiop",
                confirm_password: "qwertyuiop",
            });
            casper.click('input[name="change_settings"]');
        });
    });
});

casper.then(function () {
    casper.waitUntilVisible('#account-settings-status', function () {
        casper.test.assertSelectorHasText('#account-settings-status', 'Updated settings!');

        casper.click('[data-section="your-bots"]');
        casper.click('#api_key_button');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#get_api_key_password', function () {
        casper.fill('form[action^="/json/fetch_api_key"]', {password:'qwertyuiop'});
        casper.click('input[name="view_api_key"]');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#show_api_key_box', function () {
        casper.test.assertMatch(casper.fetchText('#api_key_value'), /[a-zA-Z0-9]{32}/, "Looks like an API key");

        // Change it all back so the next test can still log in
        casper.fill(form_sel, {
            full_name: "Iago",
            old_password: "qwertyuiop",
            new_password: test_credentials.default_user.password,
            confirm_password: test_credentials.default_user.password,
        });
        casper.click('input[name="change_settings"]');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#show_api_key_box', function () {
        casper.test.assertExists('#download_zuliprc', '~/.zuliprc button exists');
        casper.click('#download_zuliprc');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#download_zuliprc[href^="data:application"]', function () {
        casper.test.assertMatch(
            decodeURIComponent(casper.getElementsAttribute('#download_zuliprc', 'href')),
            regex_zuliprc,
            'Looks like a zuliprc file');
    });
});

casper.then(function create_bot() {
    casper.test.info('Filling out the create bot form');

    casper.fill('#create_bot_form',{
        bot_name: 'Bot 1',
        bot_short_name: '1',
        bot_default_sending_stream: 'Denmark',
        bot_default_events_register_stream: 'Rome',
    });

    casper.test.info('Submitting the create bot form');
    casper.click('#create_bot_button');
});

var bot_email;
if (REALMS_HAVE_SUBDOMAINS) {
    bot_email = '1-bot@zulip.zulipdev.com';
} else {
    bot_email = '1-bot@zulip.localhost';
}

casper.then(function () {
    var button_sel = '.download_bot_zuliprc[data-email="' + bot_email + '"]';

    casper.waitUntilVisible(button_sel, function () {
        casper.click(button_sel);

        casper.waitUntilVisible(button_sel + '[href^="data:application"]', function () {
            casper.test.assertMatch(
                decodeURIComponent(casper.getElementsAttribute(button_sel, 'href')),
                regex_zuliprc,
                'Looks like a bot ~/.zuliprc file');
        });
    });
});

casper.then(function () {
    casper.waitUntilVisible('.open_edit_bot_form[data-email="' + bot_email + '"]', function open_edit_bot_form() {
        casper.test.info('Opening edit bot form');
        casper.click('.open_edit_bot_form[data-email="' + bot_email + '"]');
    });
});

casper.then(function () {
    casper.waitUntilVisible('.edit_bot_form[data-email="' + bot_email + '"]', function test_edit_bot_form_values() {
        var form_sel = '.edit_bot_form[data-email="' + bot_email + '"]';
        casper.test.info('Testing edit bot form values');

    //     casper.test.assertEqual(
    //         common.get_form_field_value(form_sel + ' [name=bot_name]'),
    //         'Bot 1');
    //     casper.test.assertEqual(
    //         common.get_form_field_value(form_sel + ' [name=bot_default_sending_stream]'),
    //         'Denmark');
    //     casper.test.assertEqual(
    //         common.get_form_field_value(form_sel + ' [name=bot_default_events_register_stream]'),
    //         'Rome');
        casper.test.assertEqual(
            common.get_form_field_value(form_sel + ' [name=bot_name]'),
            'Bot 1');
    });
});

/*
   This test needs a modification. As it stands now, it will cause a race
   condition with all subsequent tests which access the UserProfile object
   this test modifies. Currently, if we modify alert words, we don't get
   any notification from the server, issue reported at
   https://github.com/zulip/zulip/issues/1269. Consequently, we can't wait
   on any condition to avoid the race condition.

casper.waitUntilVisible('#create_alert_word_form', function () {
    casper.test.info('Attempting to submit an empty alert word');
    casper.click('#create_alert_word_button');
    casper.test.info('Checking that an error is displayed');
    casper.test.assertVisible('#empty_alert_word_error');

    casper.test.info('Closing the error message');
    casper.click('.close-empty-alert-word-error');
    casper.test.info('Checking the error is hidden');
    casper.test.assertNotVisible('#empty_alert_word_error');

    casper.test.info('Filling out the alert word input');
    casper.sendKeys('#create_alert_word_name', 'some phrase');
    casper.click('#create_alert_word_button');

    casper.test.info('Checking that an element was created');
    casper.test.assertExists('div.alert-word-information-box');
    casper.test.assertSelectorHasText('span.value', 'some phrase');

    casper.test.info('Deleting element');
    casper.click('button.remove-alert-word');
    casper.test.info('Checking that the element was deleted');
    casper.test.assertDoesntExist('div.alert-word-information-box');
});
*/

casper.then(function change_default_language() {
    casper.test.info('Changing the default language');
    casper.click('[data-section="display-settings"]');
    casper.waitUntilVisible('#default_language');
});

casper.thenClick('#default_language');

casper.waitUntilVisible('#default_language_modal');

casper.thenClick('a[data-code="zh_Hans"]');

casper.waitUntilVisible('#display-settings-status', function () {
    casper.test.assertSelectorHasText('#display-settings-status', 'Chinese Simplified is now the default language');
    casper.test.info("Reloading the page.");
    casper.reload();
});

casper.then(function () {
    casper.waitUntilVisible("#default_language", function () {
        casper.test.info("Checking if we are on Chinese page.");
        casper.test.assertEvalEquals(function () {
            return $('#default_language_name').text();
        }, 'Chinese Simplified');
        casper.test.info("Opening German page through i18n url.");
    });
});

var settings_url = "";
if (REALMS_HAVE_SUBDOMAINS) {
    settings_url = 'http://zulip.zulipdev.com:9981/de/#settings';
} else {
    settings_url = 'http://zulipdev.com:9981/de/#settings';
}

casper.thenOpen(settings_url);

casper.waitUntilVisible("#settings-change-box", function check_url_preference() {
    casper.test.info("Checking the i18n url language precedence.");
    casper.test.assertEvalEquals(function () {
        return document.documentElement.lang;
    }, 'de');
    casper.test.info("English is now the default language");
    casper.click('[data-section="display-settings"]');
});

casper.thenClick('#default_language');

casper.waitUntilVisible('#default_language_modal');

casper.thenClick('a[data-code="en"]');

/*
 * Changing the language back to English so that subsequent tests pass.
 */
casper.waitUntilVisible('#display-settings-status', function () {
    casper.test.assertSelectorHasText('#display-settings-status', 'English ist die neue Standardsprache!  Du musst das Fenster neu laden um die Änderungen anzuwenden');
});

if (REALMS_HAVE_SUBDOMAINS) {
    settings_url = 'http://zulip.zulipdev.com:9981/';
} else {
    settings_url = 'http://zulipdev.com:9981/';
}

casper.thenOpen(settings_url);

// TODO: test the "Declare Zulip Bankruptcy option"

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
