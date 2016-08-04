var common = require('../casper_lib/common.js').common;
var test_credentials = require('../../var/casper/test_credentials.js').test_credentials;
var stream_name = "Scotland";

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Administration page');
    casper.click('a[href^="#administration"]');
});

casper.waitForSelector('#administration.tab-pane.active', function () {
    casper.test.info('Administration page is active');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#administration/, 'URL suggests we are on administration page');
});

// Test only admins may create streams Setting
casper.waitForSelector('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]', function () {
    casper.click('input[type="checkbox"][id="id_realm_create_stream_by_admins_only"]');
    casper.click('form.admin-realm-form input.btn');

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
    casper.click('form.admin-realm-form input.btn');
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
    casper.click('a[href^="#subscriptions"]');
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');

    casper.test.assertSelectorHasText("#administration a[aria-controls='deactivated-users']", "Deactivated Users");
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
            'name': 'MouseFace',
            'url': 'http://127.0.0.1:9991/static/images/integrations/logos/jenkins.png'
        });
        casper.click('form.admin-emoji-form input.btn');
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
        casper.test.assertExists('.emoji_row img[src="http://127.0.0.1:9991/static/images/integrations/logos/jenkins.png"]');
        casper.click('.emoji_row button.delete');
    });
});

casper.then(function () {
    casper.waitWhileSelector('.emoji_row', function () {
        casper.test.assertDoesntExist('.emoji_row');
    });
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
    // It matches with all the stream names which has 'O' as a substring (Rome, Scotland, Verona etc).
    // I used 'O' to make sure that it works even if there are multiple suggestions.
    // Capital 'O' is used instead of small 'o' to make sure that the suggestions are not case sensitive.
    get_suggestions("O");
    select_from_suggestions(stream_name);
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

// Test turning message editing off and on
// go to home page
casper.then(function () {
    casper.click('.global-filter[data-name="home"]');
});

// send two messages
common.then_send_message('stream', {
    stream:  'Verona',
    subject: 'edits',
    content: 'test editing 1'
});
common.then_send_message('stream', {
    stream:  'Verona',
    subject: 'edits',
    content: 'test editing 2'
});
casper.waitForText("test editing 1");
casper.waitForText("test editing 2");

// wait for message to be sent
casper.waitFor(function () {
    return casper.evaluate(function () {
        return current_msg_list.last().local_id === undefined;
    });
});

// edit the last message just sent
casper.then(function () {
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.info').click();
        $('.popover_edit_message').click();
    });
});

casper.waitForSelector(".message_edit_content", function () {
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.message_edit_content').val("test edited");
        msg.find('.message_edit_save').click();
    });
});

casper.then(function () {
    // check that the message was indeed edited
    casper.waitWhileVisible("textarea.message_edit_content", function () {
        casper.test.assertSelectorHasText(".last_message .message_content", "test edited");
    });
});

// Commented out due to Issue #1243
// // edit the same message, but don't hit save this time
// casper.then(function () {
//     casper.evaluate(function () {
//         var msg = $('#zhome .message_row:last');
//         msg.find('.info').click();
//         $('.popover_edit_message').click();
//     });
// });
// casper.waitForSelector(".message_edit_content", function () {
//     casper.evaluate(function () {
//         var msg = $('#zhome .message_row:last');
//         msg.find('.message_edit_content').val("test RE-edited");
//     });
// });

// go to admin page
casper.then(function () {
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');
});

// deactivate "allow message editing"
casper.waitForSelector('input[type="checkbox"][id="id_realm_allow_message_editing"]', function () {
    casper.click('input[type="checkbox"][id="id_realm_allow_message_editing"]');
    casper.click('form.admin-realm-form input.btn');
});

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-message-editing-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-message-editing-status', 'Users can no longer edit their past messages!');
        casper.test.assertEval(function () {
            return !(document.querySelector('input[type="checkbox"][id="id_realm_allow_message_editing"]').checked);
        }, 'Allow message editing Setting de-activated');
    });
});

// go back to home page
casper.then(function () {
    casper.click('.global-filter[data-name="home"]');
});

// Commented out due to Issue #1243
// // try to save the half-finished edit
// casper.waitForSelector('.message_table', function () {
//     casper.then(function () {
//         casper.evaluate(function () {
//             var msg = $('#zhome .message_row:last');
//             msg.find('.message_edit_save').click();
//         });
//     });
// });

// // make sure we get the right error message, and that the message hasn't actually changed
// casper.waitForSelector("div.edit_error", function () {
//     casper.test.assertSelectorHasText('div.edit_error', 'Error saving edit: Your organization has turned off message editing.');
//     casper.test.assertSelectorHasText(".last_message .message_content", "test edited");
// });

// Check that edit link no longer appears in the popover menu
// TODO: also check that the edit icon no longer appears next to the message
casper.then(function () {
    casper.waitForSelector('.message_row');
    // Note that this could have a false positive, e.g. if all the messages aren't
    // loaded yet. See Issue #1243
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.info').click();
    });
    casper.test.assertDoesntExist('.popover_edit_message');
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.info').click();
    });
});

// go back to admin page, and reactivate "allow message editing"
casper.then(function () {
    casper.click('#settings-dropdown');
    casper.click('a[href^="#administration"]');
});
casper.waitForSelector('input[type="checkbox"][id="id_realm_allow_message_editing"]', function () {
    casper.click('input[type="checkbox"][id="id_realm_allow_message_editing"]');
    casper.click('form.admin-realm-form input.btn');
    casper.waitUntilVisible('#admin-realm-message-editing-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-message-editing-status', 'Users can now edit topics for all their messages, and the content of messages which are less than 10 minutes old.');
        casper.test.assertEval(function () {
            return document.querySelector('input[type="checkbox"][id="id_realm_allow_message_editing"]').checked;
        }, 'Allow message editing Setting re-activated');
    });
});

// Commented out due to Issue #1243
// go back home
// casper.then(function () {
//     casper.click('.global-filter[data-name="home"]');
// });

// // save our edit
// casper.waitForSelector('.message_table', function () {
//     casper.then(function () {
//         casper.evaluate(function () {
//             var msg = $('#zhome .message_row:last');
//             msg.find('.message_edit_save').click();
//         });
//     });
// });

// // check that edit went through
// casper.waitWhileVisible("textarea.message_edit_content", function () {
//     casper.test.assertSelectorHasText(".last_message .message_content", "test RE-edited");
// });

// check that the edit link reappears in popover menu
// TODO check for edit icon next to message on hover
// casper.then(function () {
//     casper.evaluate(function () {
//         var msg = $('#zhome .message_row:last');
//         msg.find('.info').click();
//     });
//     casper.test.assertExists('.popover_edit_message');
//     casper.evaluate(function () {
//         var msg = $('#zhome .message_row:last');
//         msg.find('.info').click();
//     });
// });

// go to admin page
casper.then(function () {
    casper.test.info('Administration page');
    casper.click('a[href^="#administration"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#administration/, 'URL suggests we are on administration page');
    casper.test.assertExists('#administration.tab-pane.active', 'Administration page is active');
});

casper.waitForSelector('form.admin-realm-form input.btn');

// deactivate message editing
casper.waitForSelector('input[type="checkbox"][id="id_realm_allow_message_editing"]', function () {
    casper.evaluate(function () {
        $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val('4');
    });
    casper.click('input[type="checkbox"][id="id_realm_allow_message_editing"]');
    casper.click('form.admin-realm-form input.btn');
});

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-message-editing-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-message-editing-status', 'Users can no longer edit their past messages!');
        casper.test.assertEval(function () {
            return !(document.querySelector('input[type="checkbox"][id="id_realm_allow_message_editing"]').checked);
        }, 'Allow message editing Setting de-activated');
        casper.test.assertEval(function () {
            return $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val() === '4';
        }, 'Message content edit limit now 4');
    });
});

casper.then(function () {
    // allow message editing again, and check that the old edit limit is still there
    casper.waitForSelector('input[type="checkbox"][id="id_realm_allow_message_editing"]', function () {
        casper.click('input[type="checkbox"][id="id_realm_allow_message_editing"]');
        casper.click('form.admin-realm-form input.btn');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-message-editing-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-message-editing-status', 'Users can now edit topics for all their messages, and the content of messages which are less than 4 minutes old.');
        casper.test.assertEval(function () {
            return document.querySelector('input[type="checkbox"][id="id_realm_allow_message_editing"]').checked;
        }, 'Allow message editing Setting activated');
        casper.test.assertEval(function () {
            return $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val() === '4';
        }, 'Message content edit limit still 4');
    });
});

casper.then(function () {
    // allow arbitrary message editing
    casper.waitForSelector('input[type="checkbox"][id="id_realm_allow_message_editing"]', function () {
        casper.evaluate(function () {
            $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val('0');
        });
        casper.click('form.admin-realm-form input.btn');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-message-editing-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-message-editing-status', 'Users can now edit the content and topics of all their past messages!');
        casper.test.assertEval(function () {
            return document.querySelector('input[type="checkbox"][id="id_realm_allow_message_editing"]').checked;
        }, 'Allow message editing Setting still activated');
        casper.test.assertEval(function () {
            return $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val() === '0';
        }, 'Message content edit limit is 0');
    });
});

casper.then(function () {
    // disallow message editing, with illegal edit limit value. should be fixed by admin.js
    casper.waitForSelector('input[type="checkbox"][id="id_realm_allow_message_editing"]', function () {
        casper.evaluate(function () {
            $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val('moo');
        });
        casper.click('input[type="checkbox"][id="id_realm_allow_message_editing"]');
        casper.click('form.admin-realm-form input.btn');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-message-editing-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-message-editing-status', 'Users can no longer edit their past messages!');
        casper.test.assertEval(function () {
            return !(document.querySelector('input[type="checkbox"][id="id_realm_allow_message_editing"]').checked);
        }, 'Allow message editing Setting de-activated');
        casper.test.assertEval(function () {
            return $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val() === '10';
        }, 'Message content edit limit has been reset to its default');
    });
});

casper.then(function () {
    casper.test.info("Changing realm default language");
    casper.evaluate(function () {
        $('#id_realm_default_language').val('de').change();
    });
    casper.click('form.admin-realm-form input.btn');
});

casper.waitUntilVisible('#admin-realm-default-language-status', function () {
    casper.test.assertSelectorHasText('#admin-realm-default-language-status', 'Default language changed!');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
