var common = require('../casper_lib/common.js').common;

function heading(heading_str) {
    casper.then(function () {
        casper.test.info(heading_str);
    });
}

common.start_and_log_in();

// For clarity these should be different than what 08-edit uses, until
// we find a more robust way to manage DB state between tests.
var content1 = 'admin: edit test message 1';
var content2 = 'admin: edit test message 2';

// send two messages
common.then_send_message('stream', {
    stream: 'Verona',
    subject: 'edits',
    content: content1,
});
common.then_send_message('stream', {
    stream: 'Verona',
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

function submit_edit_limit_changed() {
    casper.test.assertSelectorHasText('#org-submit-msg-editing', "Save");
    casper.click('#org-submit-msg-editing');
}

// DEACTIVATE

heading("DEACTIVATE");
common.then_click("li[data-section='organization-settings']");

// deactivate "allow message editing"
casper.then(function () {
    casper.test.info("Changing message edit limit setting");
    casper.waitUntilVisible("#id_realm_msg_edit_limit_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_msg_edit_limit_setting").val("never").change();
        });
        submit_edit_limit_changed();
    });
});

casper.then(function () {
    casper.waitUntilVisible('#org-submit-msg-editing[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-msg-editing',
                                          'Saved');
        casper.test.assertEval(function () {
            return document.querySelector('#id_realm_msg_edit_limit_setting').value === "never";
        }, 'Message editing Setting disabled');
    });
});

// go back to home page
casper.then(function () {
    casper.click('.settings-header .exit');
});

// VIEW SOURCE

heading("VIEW SOURCE");
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

// REACTIVATE

heading("REACTIVATE");

// go back to admin page, and reactivate "allow message editing"
common.then_click('#settings-dropdown');
common.then_click('a[href^="#organization"]');
common.then_click("li[data-section='organization-settings']");

casper.then(function () {
    casper.test.info("Changing message edit limit setting");
    casper.waitUntilVisible("#id_realm_msg_edit_limit_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_msg_edit_limit_setting").val("upto_ten_min").change();
        });
        submit_edit_limit_changed();
    });
});

casper.then(function () {
    casper.waitUntilVisible('#org-submit-msg-editing[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-msg-editing',
                                          'Saved');
        casper.test.assertEval(function () {
            return document.querySelector('#id_realm_msg_edit_limit_setting').value === "upto_ten_min";
        }, 'Allow message editing Setting re-activated and set to 10 minutes');
    });
});

// SET LIMIT TO 1 WEEK
heading("LIMIT TO 1 WEEK");

casper.then(function () {
    casper.test.info("Changing message edit limit setting");
    casper.waitUntilVisible("#id_realm_msg_edit_limit_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_msg_edit_limit_setting").val("upto_one_week").change();
        });
        submit_edit_limit_changed();
    });
});

casper.then(function () {
    casper.waitUntilVisible('#org-submit-msg-editing[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-msg-editing',
                                          'Saved');
        casper.test.assertEval(function () {
            return document.querySelector('#id_realm_msg_edit_limit_setting').value === "upto_one_week";
        }, 'Message edit limit set to one week');
    });
});

// SET LIMIT TO 0
heading("NO LIMIT");

casper.then(function () {
    casper.test.info("Changing message edit limit setting");
    casper.waitUntilVisible("#id_realm_msg_edit_limit_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_msg_edit_limit_setting").val("any_time").change();
        });
        submit_edit_limit_changed();
    });
});

casper.then(function () {
    casper.waitUntilVisible('#org-submit-msg-editing[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-msg-editing',
                                          'Saved');
        casper.test.assertEval(function () {
            return document.querySelector('#id_realm_msg_edit_limit_setting').value === "any_time";
        }, 'Message can be edited any time');
    });
});

// CUSTOM LIMIT
heading("CUSTOM LIMIT");

casper.then(function () {
    casper.test.info("Changing message edit limit setting");
    casper.waitUntilVisible("#id_realm_msg_edit_limit_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_msg_edit_limit_setting").val("custom_limit").change();
        });
    });
    casper.waitUntilVisible('#id_realm_message_content_edit_limit_minutes', function () {
        casper.evaluate(function () {
            $('#id_realm_message_content_edit_limit_minutes').val("100");
        });
        submit_edit_limit_changed();
    });
});

casper.then(function () {
    casper.waitUntilVisible('#org-submit-msg-editing[data-status="saved"]', function () {
        casper.test.assertSelectorHasText('#org-submit-msg-editing',
                                          'Saved');
        casper.test.assertEval(function () {
            return $('#id_realm_msg_edit_limit_setting').val() === "custom_limit";
        }, 'Custom message edit limit set');
        casper.test.assertEval(function () {
            return $('#id_realm_message_content_edit_limit_minutes').val() === "100";
        }, 'Message edit limit set to 100 minutes');
    });
});

// INVALID LIMIT
heading("INVALID LIMIT");

casper.then(function () {
    casper.test.info("Changing message edit limit setting");
    casper.waitUntilVisible("#id_realm_msg_edit_limit_setting", function () {
        casper.evaluate(function () {
            $("#id_realm_msg_edit_limit_setting").val("custom_limit").change();
        });
    });
    casper.waitUntilVisible('#id_realm_message_content_edit_limit_minutes', function () {
        casper.evaluate(function () {
            $('#id_realm_message_content_edit_limit_minutes').val("-100");
        });
        submit_edit_limit_changed();
    });
});

casper.then(function () {
    casper.waitUntilVisible('#org-msg-editing .subsection-failed-status', function () {
        casper.test.assertSelectorHasText('#org-submit-msg-editing',
                                          'Save');
    });
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
