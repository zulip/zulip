var common = require('../casper_lib/common.js').common;


function submit_checked() {
    casper.then(function () {
        casper.waitUntilVisible('input:checked[type="checkbox"][id="id_realm_allow_message_editing"] + span', function () {
            casper.click('form.org-settings-form button.button');
        });
    });
}

function submit_unchecked() {
    casper.then(function () {
        casper.waitUntilVisible('input:not(:checked)[type="checkbox"][id="id_realm_allow_message_editing"] + span', function () {
            casper.click('form.org-settings-form button.button');
        });
    });
}

common.start_and_log_in();

// For clarity these should be different than what 08-edit uses, until
// we find a more robust way to manage DB state between tests.
var content1 = 'admin: edit test message 1';
var content2 = 'admin: edit test message 2';

// send two messages
common.then_send_message('stream', {
    stream:  'Verona',
    subject: 'edits',
    content: content1,
});
common.then_send_message('stream', {
    stream:  'Verona',
    subject: 'edits',
    content: content2,
});

casper.then(function () {
    casper.waitForSelectorText('#zhome .message_row', content1);
    casper.waitForSelectorText('#zhome .message_row', content2);
});

// wait for message to be sent
casper.then(function () {
    casper.waitFor(function () {
        return casper.evaluate(function () {
            return !current_msg_list.last().locally_echoed;
        });
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

var edited_value = 'admin tests: test edit';

casper.then(function () {
    casper.waitUntilVisible(".message_edit_content", function () {
        casper.evaluate(function (edited_value) {
            var msg = $('#zhome .message_row:last');
            msg.find('.message_edit_content').val(edited_value);
            msg.find('.message_edit_save').click();
        }, edited_value);
    });
});

casper.then(function () {
    // check that the message was indeed edited
    casper.waitWhileVisible("textarea.message_edit_content", function () {
        casper.test.assertSelectorHasText(".last_message .message_content", edited_value);
    });
});

// go to admin page
common.then_click('#settings-dropdown');
common.then_click('a[href^="#organization"]');

casper.then(function () {
    casper.waitForSelector('#settings_overlay_container.show', function () {
        casper.test.info('Organization page is active');
        casper.test.assertUrlMatch(/^http:\/\/[^/]+\/#organization/, 'URL suggests we are on organization page');
    });
});

common.then_click("li[data-section='organization-settings']");

// deactivate "allow message editing"
common.then_click('input[type="checkbox"][id="id_realm_allow_message_editing"] + span');

submit_unchecked();

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
    casper.click('.settings-header .exit');
});

// Check that edit link has changed to "View source" in the popover menu
// TODO: also check that the edit icon no longer appears next to the message
casper.then(function () {
    // This somehow makes the "View source" test deterministic. It seems that
    // we are waiting on a wrong condition somewhere.
    casper.wait(1000);
});

casper.then(function () {
    casper.waitUntilVisible('.message_row');
    // Note that this could have a false positive, e.g. if all the messages aren't
    // loaded yet. See Issue #1243
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.info').click();
    });
    casper.waitUntilVisible('.popover_edit_message', function () {
        casper.test.assertSelectorHasText('.popover_edit_message', 'View source');
    });
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.info').click();
    });
});

// go back to admin page, and reactivate "allow message editing"
common.then_click('#settings-dropdown');
common.then_click('a[href^="#organization"]');
common.then_click("li[data-section='organization-settings']");
common.then_click('input[type="checkbox"][id="id_realm_allow_message_editing"] + span');
submit_checked();

casper.then(function () {
    casper.waitUntilVisible('#admin-realm-message-editing-status', function () {
        casper.test.assertSelectorHasText('#admin-realm-message-editing-status', 'Users can now edit topics for all their messages, and the content of messages which are less than 10 minutes old.');
        casper.test.assertEval(function () {
            return document.querySelector('input[type="checkbox"][id="id_realm_allow_message_editing"]').checked;
        }, 'Allow message editing Setting re-activated');
    });
});


// go to admin page
casper.then(function () {
    casper.test.info('Organization page');
    casper.click('a[href^="#organization"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#organization/, 'URL suggests we are on organization page');
    casper.test.assertExists('#settings_overlay_container.show', 'Organization page is active');
});

casper.then(function () {
    casper.waitUntilVisible('form.admin-realm-form button.button');
});

// deactivate message editing
casper.then(function () {
    casper.waitUntilVisible('input[type="checkbox"][id="id_realm_allow_message_editing"] + span', function () {
        casper.evaluate(function () {
            $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val('4');
        });
    });
});

common.then_click('input[type="checkbox"][id="id_realm_allow_message_editing"] + span');
submit_unchecked();

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

common.then_click('input[type="checkbox"][id="id_realm_allow_message_editing"] + span');
submit_checked();

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
    casper.waitUntilVisible('input[type="checkbox"][id="id_realm_allow_message_editing"] + span', function () {
        casper.evaluate(function () {
            $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val('0');
        });
        casper.click('form.org-settings-form button.button');
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
    casper.waitUntilVisible('input[type="checkbox"][id="id_realm_allow_message_editing"] + span', function () {
        casper.evaluate(function () {
            $('input[type="text"][id="id_realm_message_content_edit_limit_minutes"]').val('moo');
        });
        casper.click('input[type="checkbox"][id="id_realm_allow_message_editing"] + span');
        casper.click('form.org-settings-form button.button');
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

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
