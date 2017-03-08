var common = require('../casper_lib/common.js').common;

function waitWhileDraftsVisible(then) {
    casper.waitFor(function () {
        return casper.evaluate(function () {
            return $("#draft_overlay").length === 0 ||
                   $("#draft_overlay").css("opacity") === "0";
        });
    }, then);
}

function waitUntilDraftsVisible(then) {
    casper.waitFor(function () {
        return casper.evaluate(function () {
            return $("#draft_overlay").length === 1 &&
                   $("#draft_overlay").css("opacity") === "1";
        });
    }, then);
}

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Drafts page');

    casper.waitUntilVisible('.drafts-link', function () {
        casper.click('.drafts-link');
    });
});

casper.then(function () {
    casper.test.assertUrlMatch(/^http:\/\/[^/]+\/#drafts/,
                               'URL suggests we are on drafts page');
    waitUntilDraftsVisible(function () {
        casper.test.assertExists('#draft_overlay', 'Drafts page is active');
        casper.test.assertSelectorHasText('.no-drafts', 'No drafts.');
    });
});


casper.then(function () {
    casper.click('#draft_overlay .exit');
    waitWhileDraftsVisible();
});

casper.then(function () {
    casper.test.info('Creating Stream Message Draft');
    casper.click('body');
    casper.page.sendEvent('keypress', "c");
    casper.waitUntilVisible('#stream-message', function () {
        casper.test.info('Creating Private Message Draft');
        casper.fill('form#send_message_form', {
            stream: 'all',
            subject: 'tests',
            content: 'Test Stream Message',
        }, false);
        casper.click("#compose_close");
    });
});

casper.then(function () {
    casper.test.info('Creating Private Message Draft');
    casper.click('body');
    casper.page.sendEvent('keypress', "C");
    casper.waitUntilVisible('#private-message', function () {
        casper.fill('form#send_message_form', {
            recipient: 'cordelia@zulip.com, hamlet@zulip.com',
            content: 'Test Private Message',
        }, false);
        casper.click("#compose_close");
    });
});

casper.then(function () {
    casper.waitUntilVisible('.drafts-link', function () {
        casper.click('.drafts-link');
    });
});

casper.then(function () {
    waitUntilDraftsVisible(function () {
        casper.test.assertElementCount('.draft-row', 2, 'Drafts loaded');

        casper.test.assertSelectorHasText('.draft-row .message_header_stream .stream_label', 'all');
        casper.test.assertSelectorHasText('.draft-row .message_header_stream .stream_topic', 'tests');
        casper.test.assertTextExists('Test Stream Message', 'Stream draft contains message content');

        casper.test.assertSelectorHasText('.draft-row .message_header_private_message .stream_label',
                                          'You and Cordelia Lear, King Hamlet');
        casper.test.assertTextExists('Test Private Message', 'Private draft contains message content');
    });
});

casper.then(function () {
    casper.test.info('Restoring Stream Message Draft');
    casper.click("#drafts_table .message_row:not(.private-message) .restore-draft");
    waitWhileDraftsVisible(function () {
        casper.test.assertVisible('#stream-message', 'Stream Message Box Restored');
        common.check_form('form#send_message_form', {
            stream: 'all',
            subject: 'tests',
            content: 'Test Stream Message',
        }, "Stream message box filled with draft content");
    });
});

casper.then(function () {
    casper.test.info('Editing Stream Message Draft');
    casper.fill('form#send_message_form', {
        stream: 'all',
        subject: 'tests',
        content: 'Updated Stream Message',
    }, false);
    casper.click("#compose_close");
});

casper.then(function () {
    casper.waitUntilVisible('.drafts-link', function () {
        casper.click('.drafts-link');
    });
});

casper.then(function () {
    waitUntilDraftsVisible(function () {
        casper.test.assertSelectorHasText('.draft-row .message_header_stream .stream_label', 'all');
        casper.test.assertSelectorHasText('.draft-row .message_header_stream .stream_topic', 'tests');
        casper.test.assertTextExists('Updated Stream Message', 'Stream draft contains message content');
    });
});

casper.then(function () {
    casper.test.info('Restoring Private Message Draft');
    casper.click("#drafts_table .message_row.private-message .restore-draft");
    waitWhileDraftsVisible(function () {
        casper.test.assertVisible('#private-message', 'Private Message Box Restored');
        common.check_form('form#send_message_form', {
            recipient: 'cordelia@zulip.com, hamlet@zulip.com',
            content: 'Test Private Message',
        }, "Private message box filled with draft content");
    });
});

casper.then(function () {
    casper.click("#compose_close");
    casper.waitUntilVisible('.drafts-link', function () {
        casper.click('.drafts-link');
    });
});

casper.then(function () {
    casper.test.info('Deleting Draft');
    casper.click("#drafts_table .message_row.private-message .delete-draft");
    casper.test.assertElementCount('.draft-row', 1, 'Draft deleted');
    casper.test.assertDoesntExist("#drafts_table .message_row.private-message");
});

casper.then(function () {
    casper.test.info('Saving Draft by Reloading');
    casper.click('#draft_overlay .exit');
    waitWhileDraftsVisible(function () {
        casper.click('body');
        casper.page.sendEvent('keypress', "C");
        casper.waitUntilVisible('#private-message', function () {
            casper.fill('form#send_message_form', {
                recipient: 'cordelia@zulip.com',
                content: 'Test Private Message',
            }, false);
            casper.reload();
        });
    });
});

casper.then(function () {
    casper.waitUntilVisible('.drafts-link', function () {
        casper.click('.drafts-link');
    });
    waitUntilDraftsVisible(function () {
        casper.test.assertElementCount('.draft-row', 2, 'Drafts loaded');
        casper.test.assertSelectorHasText('.draft-row .message_header_private_message .stream_label',
                                          'You and Cordelia Lear');
        casper.test.assertTextExists('Test Private Message');
    });
});

casper.then(function () {
    casper.test.info('Deleting Draft after Sending Message');
    casper.click("#drafts_table .message_row.private-message .restore-draft");
    waitWhileDraftsVisible(function () {
        casper.test.assertVisible('#private-message');
        casper.click('#compose-send-button');
    });
});

casper.then(function () {
    // This tests the second drafts link in the compose area
    casper.waitUntilVisible('.compose_table .drafts-link', function () {
        casper.click('.compose_table .drafts-link');
    });
    waitUntilDraftsVisible(function () {
        casper.test.assertElementCount('.draft-row', 1, 'Drafts loaded');
        casper.test.assertDoesntExist("#drafts_table .message_row.private-message");
    });
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
