var common = require('../casper_lib/common.js').common;
var test_credentials = require('../../var/casper/test_credentials.js').test_credentials;
var OUTGOING_WEBHOOK_BOT_TYPE = '3';

common.start_and_log_in();

// Password change form test commented out due to Django logging out the user.

// var form_sel = 'form[action^="/json/settings"]';
var regex_zuliprc = /^data:application\/octet-stream;charset=utf-8,\[api\]\nemail=.+\nkey=.+\nsite=.+\n$/;
var regex_flaskbotrc = /^data:application\/octet-stream;charset=utf-8,\[.\]\nemail=.+\nkey=.+\nsite=.+\n$/;

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

        // casper.click(".change_password_button");
        casper.click('#api_key_button');
    });
});

/*
casper.then(function () {
    casper.waitUntilVisible("#pw_change_controls", function () {
        casper.waitForResource("zxcvbn.js", function () {
            casper.test.assertVisible("#old_password");
            casper.test.assertVisible("#new_password");

            casper.test.assertEqual(casper.getFormValues(form_sel).full_name, "Iago");

            casper.fill(form_sel, {
                full_name: "IagoNew",
                old_password: test_credentials.default_user.password,
                new_password: "qwertyuiop",
            });
            casper.test.assertNotVisible("#account-settings-status");
            casper.click('button[name="change_settings"]');
        });
    });
});

casper.then(function () {
    casper.waitUntilVisible('#account-settings-status', function () {
        casper.test.assertSelectorHasText('#account-settings-status', 'Updated settings!');
        casper.click('#api_key_button');
    });
});
*/

casper.then(function () {
    casper.waitUntilVisible('#get_api_key_password', function () {
        casper.fill('form[action^="/json/fetch_api_key"]', {password:test_credentials.default_user.password});
        casper.click('button[name="view_api_key"]');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#show_api_key_box', function () {
        casper.test.assertMatch(casper.fetchText('#api_key_value'), /[a-zA-Z0-9]{32}/, "Looks like an API key");

        /*
        // Change it all back so the next test can still log in
        casper.fill(form_sel, {
            full_name: "Iago",
            old_password: "qwertyuiop",
            new_password: test_credentials.default_user.password,
        });
        casper.click('button[name="change_settings"]');
        */
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

casper.then(function () {
    // casper.waitUntilVisible('#account-settings-status', function () {
    casper.click('[data-section="your-bots"]');
    // });
});

casper.then(function create_bot() {
    casper.test.info('Filling out the create bot form');

    casper.fill('#create_bot_form',{
        bot_name: 'Bot 1',
        bot_short_name: '1',
        bot_type: OUTGOING_WEBHOOK_BOT_TYPE,
        payload_url: 'http://hostname.example.com/bots/followup',
    });

    casper.test.info('Submitting the create bot form');
    casper.click('#create_bot_button');
});

var bot_email = '1-bot@zulip.zulipdev.com';
var button_sel = '.download_bot_zuliprc[data-email="' + bot_email + '"]';

casper.then(function () {
    casper.waitUntilVisible(button_sel, function () {
        casper.click(button_sel);
    });
});

casper.then(function () {
    casper.waitUntilVisible(button_sel + '[href^="data:application"]', function () {
        casper.test.assertMatch(
            decodeURIComponent(casper.getElementsAttribute(button_sel, 'href')),
            regex_zuliprc,
            'Looks like a bot ~/.zuliprc file');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#download_flaskbotrc', function () {
        casper.click("#download_flaskbotrc");

        casper.waitUntilVisible('#download_flaskbotrc[href^="data:application"]', function () {
            casper.test.assertMatch(
                decodeURIComponent(casper.getElementsAttribute('#download_flaskbotrc', 'href')),
                regex_flaskbotrc,
                'Looks like a flaskbotrc file');
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

casper.then(function () {
    casper.click('[data-section="alert-words"]');
    casper.waitUntilVisible('#create_alert_word_form', function () {
        casper.test.info('Attempting to submit an empty alert word');
        casper.click('#create_alert_word_button');
        casper.waitUntilVisible('#alert_word_status', function () {
            casper.test.info('Checking that an error is displayed');
            casper.test.assertSelectorHasText('.alert_word_status_text', 'Alert word can\'t be empty!');
            casper.test.info('Closing the error message');
            casper.click('.close-alert-word-status');
            casper.test.info('Checking the error is hidden');
            casper.test.assertNotVisible('#alert_word_status');
        });
    });
});

casper.then(function () {
    casper.test.info('Filling out the alert word input');
    casper.sendKeys('#create_alert_word_name', 'some phrase');
    casper.click('#create_alert_word_button');
    casper.test.info('Checking that a success message is displayed');
    casper.waitUntilVisible('#alert_word_status', function () {
        casper.test.assertSelectorHasText('.alert_word_status_text', 'Alert word added successfully!');
        casper.test.info('Closing the status message');
        casper.click('.close-alert-word-status');
        casper.test.info('Checking the status message is hidden');
        casper.test.assertNotVisible('#alert_word_status');
    });
});

casper.then(function () {
    casper.test.info('Checking that an element was created');
    casper.waitUntilVisible(".alert-word-item[data-word='some phrase']", function () {
        casper.test.assertExists('div.alert-word-information-box');
        casper.test.assertSelectorHasText('span.value', 'some phrase');
    });
});

casper.then(function () {
    casper.test.info('Trying to create a duplicate alert word');
    casper.sendKeys('#create_alert_word_name', 'some phrase');
    casper.click('#create_alert_word_button');
    casper.test.info('Checking that an error message is displayed');
    casper.waitUntilVisible('#alert_word_status', function () {
        casper.test.assertSelectorHasText('.alert_word_status_text', 'Alert word already exists!');
        casper.test.info('Closing the status message');
        casper.click('.close-alert-word-status');
        casper.test.info('Checking the status message is hidden');
        casper.test.assertNotVisible('#alert_word_status');
    });
});

casper.then(function () {
    casper.test.info('Deleting alert word');
    casper.click('button.remove-alert-word');
    casper.test.info('Checking that a success message is displayed');
    casper.waitUntilVisible('#alert_word_status', function () {
        casper.test.assertSelectorHasText('.alert_word_status_text', 'Alert word removed successfully!');
        casper.test.info('Closing the status message');
        casper.click('.close-alert-word-status');
        casper.test.info('Checking the status message is hidden');
        casper.test.assertNotVisible('#alert_word_status');
    });
    casper.test.info('Checking that the element was deleted');
    casper.waitWhileVisible(".alert-word-item[data-word='some phrase']", function () {
        casper.test.assertDoesntExist('div.alert-word-information-box');
        casper.test.info('Element deleted successfully');
    });
});

casper.then(function change_default_language() {
    casper.test.info('Changing the default language');
    casper.click('[data-section="display-settings"]');
    casper.waitUntilVisible('#default_language');
});

casper.thenClick('#default_language');

casper.waitUntilVisible('#default_language_modal');

casper.thenClick('a[data-code="zh-hans"]');

casper.waitUntilVisible('#language-settings-status a', function () {
    casper.test.assertSelectorHasText('#language-settings-status', 'Saved. Please reload for the change to take effect.');
    casper.test.info("Reloading the page.");
    casper.reload();
});

casper.then(function () {
    casper.waitUntilVisible("#default_language", function () {
        casper.test.info("Checking if we are on Chinese page.");
        casper.test.assertEvalEquals(function () {
            return $('#default_language_name').text().trim();
        }, '简体中文');
        casper.test.info("Opening German page through i18n url.");
    });
});

var settings_url = 'http://zulip.zulipdev.com:9981/de/#settings';

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
casper.waitUntilVisible('#language-settings-status a', function () {
    casper.test.assertSelectorHasText('#language-settings-status', 'Gespeichert. Bitte lade die Seite neu um die Änderungen zu aktivieren.');
});

casper.thenOpen("http://zulip.zulipdev.com:9981/");

// TODO: test the "Declare Zulip Bankruptcy option"

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
