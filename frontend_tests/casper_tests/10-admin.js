var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    var menu_selector = '#settings-dropdown';
    casper.waitUntilVisible(menu_selector, function () {
        casper.click(menu_selector);
    });
});

casper.then(function () {
    casper.test.info('Administration page');
    casper.click('a[href^="#administration"]');
});

casper.waitForSelector('#administration.tab-pane.active', function () {
    casper.test.info('Administration page is active');
    casper.test.assertUrlMatch(/^http:\/\/[^/]+\/#administration/, 'URL suggests we are on administration page');
});

// Test only admins may create streams Setting
casper.waitForSelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]', function () {
    casper.click('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]');
    casper.click('form.admin-realm-form input.button');

});

casper.then(function () {
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
});

casper.waitForSelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]', function () {
    // Test Setting was saved
    casper.test.assertEval(function () {
        return document.querySelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]').checked;
    }, 'Only admins may create streams Setting saved');

    // Deactivate setting
    casper.click('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]');
    casper.click('form.admin-realm-form input.button');
});

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-create-stream-by-admins-only-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-create-stream-by-admins-only-status', 'Any user may now create new streams!');
        casper.test.assertEval(function () {
            return !(document.querySelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]').checked);
        }, 'Only admins may create streams Setting deactivated');
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

casper.then(function () {
    // Test custom realm emoji
    casper.waitForSelector('.admin-emoji-form', function () {
        casper.fill('form.admin-emoji-form', {
            name: 'MouseFace',
            url: 'http://zulipdev.com:9991/static/images/integrations/logos/jenkins.png',
        });
        casper.click('form.admin-emoji-form input.button');
    });
});

casper.then(function () {
    casper.waitUntilVisible('div#admin-emoji-status', function () {
        casper.test.assertSelectorHasText('div#admin-emoji-status', 'Custom emoji added!');
    });
});

casper.then(function () {
    casper.waitForSelector('.emoji_row', function () {
        casper.test.assertSelectorHasText('.emoji_row .emoji_name', 'MouseFace');
        casper.test.assertExists('.emoji_row img[src="http://zulipdev.com:9991/static/images/integrations/logos/jenkins.png"]');
        casper.click('.emoji_row button.delete');
    });
});

casper.then(function () {
    casper.waitWhileSelector('.emoji_row', function () {
        casper.test.assertDoesntExist('.emoji_row');
    });
});

// Test custom realm filters
casper.then(function () {
    casper.waitForSelector('.admin-filter-form', function () {
        casper.fill('form.admin-filter-form', {
            pattern: '#(?P<id>[0-9]+)',
            url_format_string: 'https://trac.example.com/ticket/%(id)s',
        });
        casper.click('form.admin-filter-form input.btn');
    });
});

casper.then(function () {
    casper.waitUntilVisible('div#admin-filter-status', function () {
        casper.test.assertSelectorHasText('div#admin-filter-status', 'Custom filter added!');
    });
});

casper.then(function () {
    casper.waitForSelector('.filter_row', function () {
        casper.test.assertSelectorHasText('.filter_row span.filter_pattern', '#(?P<id>[0-9]+)');
        casper.test.assertSelectorHasText('.filter_row span.filter_url_format_string', 'https://trac.example.com/ticket/%(id)s');
        casper.click('.filter_row button');
    });
});

casper.then(function () {
    casper.waitWhileSelector('.filter_row', function () {
        casper.test.assertDoesntExist('.filter_row');
    });
});

casper.then(function () {
    casper.waitForSelector('.admin-filter-form', function () {
        casper.fill('form.admin-filter-form', {
            pattern: 'a$',
            url_format_string: 'https://trac.example.com/ticket/%(id)s',
        });
        casper.click('form.admin-filter-form input.btn');
    });
});

casper.then(function () {
    casper.waitUntilVisible('div#admin-filter-pattern-status', function () {
        casper.test.assertSelectorHasText('div#admin-filter-pattern-status', 'Failed: Invalid filter pattern, you must use the following format OPTIONAL_PREFIX(?P<id>.+)');
    });
});

var stream_name = "Scotland";
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
                currentTarget: $('.typeahead:visible li:contains("'+item+'")')[0],
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
    casper.waitUntilVisible(".create_default_stream", function () {
        // It matches with all the stream names which has 'O' as a substring (Rome, Scotland, Verona
        // etc). 'O' is used to make sure that it works even if there are multiple suggestions.
        // Uppercase 'O' is used instead of the lowercase version to make sure that the suggestions
        // are case insensitive.
        get_suggestions("O");
        select_from_suggestions(stream_name);
    });
});

casper.then(function () {
    casper.waitForSelector('.default_stream_row[id='+stream_name+']', function () {
        casper.test.assertSelectorHasText('.default_stream_row[id='+stream_name+'] .default_stream_name', stream_name);
    });
});

casper.then(function () {
    casper.waitForSelector('.default_stream_row[id='+stream_name+']', function () {
        casper.test.assertSelectorHasText('.default_stream_row[id='+stream_name+'] .default_stream_name', stream_name);
        casper.click('.default_stream_row[id='+stream_name+'] button.remove-default-stream');
    });
});

casper.then(function () {
    casper.waitWhileSelector('.default_stream_row[id='+stream_name+']', function () {
        casper.test.assertDoesntExist('.default_stream_row[id='+stream_name+']');
    });
});

// TODO: Test stream deletion

casper.then(function () {
    casper.waitUntilVisible('#id_realm_default_language', function () {
        casper.test.info("Changing realm default language");
        casper.evaluate(function () {
            $('#id_realm_default_language').val('de').change();
        });
        casper.click('form.admin-realm-form input.button');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-default-language-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-default-language-status',
                                          'Default language changed!');
    });
});

// Test authentication methods setting
casper.then(function () {
    casper.waitForSelector(".method_row[data-method='Email'] input[type='checkbox']", function () {
        casper.click(".method_row[data-method='Email'] input[type='checkbox']");
        casper.click('form.admin-realm-form input.button');
    });
});

// Test setting was activated--default is checked
casper.then(function () {
    // Scroll to bottom so that casper snapshots show the auth methods table
    this.scrollToBottom();
    // Test setting was activated
    casper.waitUntilVisible('#admin-realm-authentication-methods-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-authentication-methods-status', 'Authentication methods saved!');
        casper.test.assertEval(function () {
            return !(document.querySelector(".method_row[data-method='Email'] input[type='checkbox']").checked);
        });
    });
});

casper.then(function () {
    // Leave the page and return
    casper.click('#settings-dropdown');
    casper.click('a[href^="#subscriptions"]');
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');

    casper.waitForSelector(".method_row[data-method='Email'] input[type='checkbox']", function () {
        // Test Setting was saved
        casper.test.assertEval(function () {
            return !(document.querySelector(".method_row[data-method='Email'] input[type='checkbox']").checked);
        });
    });
});

// Deactivate setting--default is checked
casper.then(function () {
    casper.click(".method_row[data-method='Email'] input[type='checkbox']");
    casper.click('form.admin-realm-form input.button');
    casper.waitUntilVisible('#admin-realm-authentication-methods-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-authentication-methods-status', 'Authentication methods saved!');
        casper.test.assertEval(function () {
            return document.querySelector(".method_row[data-method='Email'] input[type='checkbox']").checked;
        });
    });
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
