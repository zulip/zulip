var common = require('../casper_lib/common.js').common;
var test_credentials = require('../casper_lib/test_credentials.js').test_credentials;

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Administration page');
    casper.click('a[href^="#administration"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#administration/, 'URL suggests we are on administration page');
    casper.test.assertExists('#administration.tab-pane.active', 'Administration page is active');
});

// Test only admins may create streams Setting
casper.waitForSelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]', function () {
    casper.click('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]');
    casper.click('form.admin-realm-form input.btn');

    // Test setting was activated
    casper.waitUntilVisible('#admin-realm-create-stream-by-admins-only-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-create-stream-by-admins-only-status', 'Only Admins may now create new streams!');
        casper.test.assertEval(function () {
            return document.querySelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]').checked;
        }, 'Only admins may create streams Setting activated');
    });
});

casper.then(function () {
    // Leave the page and return
    casper.click('#settings-dropdown');
    casper.click('a[href^="#subscriptions"]');
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');

    casper.waitForSelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]', function () {
        // Test Setting was saved
        casper.test.assertEval(function () {
            return document.querySelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]').checked;
        }, 'Only admins may create streams Setting saved');

        // Deactivate setting
        casper.click('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]');
        casper.click('form.admin-realm-form input.btn');
        casper.waitUntilVisible('#admin-realm-create-stream-by-admins-only-status', function () {
            casper.test.assertSelectorHasText('#admin-realm-create-stream-by-admins-only-status', 'Any user may now create new streams!');
            casper.test.assertEval(function () {
                return !(document.querySelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]').checked);
            }, 'Only admins may create streams Setting deactivated');
        });
    });
});

// Test user deactivation and reactivation
casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"]', function () {
    casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
    casper.click('.user_row[id="user_cordelia@zulip.com"] .deactivate');
    casper.test.assertTextExists('Deactivate cordelia@zulip.com', 'Deactivate modal has right user');
    casper.test.assertTextExists('Deactivate now', 'Deactivate now button available');
    casper.click('#do_deactivate_user_button');
});

casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"].deactivated_user', function () {
    casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Reactivate');
    casper.click('.user_row[id="user_cordelia@zulip.com"] .reactivate');
});

casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"]:not(.deactivated_user)', function () {
    casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
});

// Test Deactivated users section of admin page
casper.waitForSelector('.user_row[id="user_cordelia@zulip.com"]', function () {
    casper.test.assertSelectorHasText('.user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
    casper.click('.user_row[id="user_cordelia@zulip.com"] .deactivate');
    casper.test.assertTextExists('Deactivate cordelia@zulip.com', 'Deactivate modal has right user');
    casper.test.assertTextExists('Deactivate now', 'Deactivate now button available');
    casper.click('#do_deactivate_user_button');
});

casper.then(function () {
    // Leave the page and return
    casper.click('#settings-dropdown');
    casper.click('a[href^="#subscriptions"]');
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');

    casper.test.assertSelectorHasText("#administration a[aria-controls='deactivated-users']", "Deactivated Users");
    casper.click("#administration a[aria-controls='deactivated-users']");


    casper.waitForSelector('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"] .reactivate', function () {
        casper.test.assertSelectorHasText('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"]', 'Reactivate');
        casper.click('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"] .reactivate');
    });

    casper.waitForSelector('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"] button:not(.reactivate)', function () {
        casper.test.assertSelectorHasText('#admin_deactivated_users_table .user_row[id="user_cordelia@zulip.com"]', 'Deactivate');
    });

    casper.test.assertSelectorHasText("#administration a[aria-controls='organization']", "Organization");
    casper.click("#administration a[aria-controls='organization']");
});

// Test bot deactivation and reactivation
casper.waitForSelector('.user_row[id="user_new-user-bot@zulip.com"]', function () {
    casper.test.assertSelectorHasText('.user_row[id="user_new-user-bot@zulip.com"]', 'Deactivate');
    casper.click('.user_row[id="user_new-user-bot@zulip.com"] .deactivate');
});

casper.waitForSelector('.user_row[id="user_new-user-bot@zulip.com"].deactivated_user', function () {
    casper.test.assertSelectorHasText('.user_row[id="user_new-user-bot@zulip.com"]', 'Reactivate');
    casper.click('.user_row[id="user_new-user-bot@zulip.com"] .reactivate');
});
casper.waitForSelector('.user_row[id="user_new-user-bot@zulip.com"]:not(.deactivated_user)', function () {
    casper.test.assertSelectorHasText('.user_row[id="user_new-user-bot@zulip.com"]', 'Deactivate');
});

// Test custom realm emoji
casper.waitForSelector('.admin-emoji-form', function () {
    casper.fill('form.admin-emoji-form', {
        'name': 'MouseFace',
        'url': 'http://localhost:9991/static/images/integrations/logos/jenkins.png'
    });
    casper.click('form.admin-emoji-form input.btn');
});

casper.waitUntilVisible('div#admin-emoji-status', function () {
    casper.test.assertSelectorHasText('div#admin-emoji-status', 'Custom emoji added!');
});

casper.waitForSelector('.emoji_row', function () {
    casper.test.assertSelectorHasText('.emoji_row .emoji_name', 'MouseFace');
    casper.test.assertExists('.emoji_row img[src="http://localhost:9991/static/images/integrations/logos/jenkins.png"]');
    casper.click('.emoji_row button.delete');
});

casper.waitWhileSelector('.emoji_row', function () {
    casper.test.assertDoesntExist('.emoji_row');
});

function get_suggestions(str) {
    casper.then(function () {
        casper.evaluate(function (str) {
            $('.create_default_stream')
            .focus()
            .val(str)
            .trigger($.Event('keyup', { which: 0 }));
        }, str);
    });
}

function select_from_suggestions(item) {
    casper.then(function () {
        casper.evaluate(function (item) {
            var tah = $('.create_default_stream').data().typeahead;
            tah.mouseenter({
                currentTarget: $('.typeahead:visible li:contains("'+item+'")')[0]
            });
            tah.select();
        }, {item: item});
    });
}

// Test default stream creation and addition
casper.then(function () {
    casper.click('#settings-dropdown');
    casper.click('a[href^="#subscriptions"]');
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');
    var stream_name = "Scotland";
    // It matches with all the stream names which has 'O' as a substring (Rome, Scotland, Verona etc).
    // I used 'O' to make sure that it works even if there are multiple suggestions.
    // Capital 'O' is used instead of small 'o' to make sure that the suggestions are not case sensitive.
    get_suggestions("O");
    select_from_suggestions(stream_name);
    casper.waitForSelector('.default_stream_row[id='+stream_name+']', function () {
        casper.test.assertSelectorHasText('.default_stream_row[id='+stream_name+'] .default_stream_name', stream_name);
    });
    casper.waitForSelector('.default_stream_row[id='+stream_name+']', function () {
        casper.test.assertSelectorHasText('.default_stream_row[id='+stream_name+'] .default_stream_name', stream_name);
        casper.click('.default_stream_row[id='+stream_name+'] button.remove-default-stream');
    });
    casper.waitWhileSelector('.default_stream_row[id='+stream_name+']', function () {
        casper.test.assertDoesntExist('.default_stream_row[id='+stream_name+']');
    });
});
// TODO: Test stream deletion

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
