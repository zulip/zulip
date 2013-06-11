var common = require('../common.js').common;

common.start_and_log_in();

// Send a message to try replying to
common.send_message('stream', {
    stream: 'Verona',
    subject: 'Reply test',
    content: "We reply to this message"
});
common.send_message('private', {
    recipient: "cordelia@humbughq.com",
    content: "And reply to this message"
});
casper.waitForText("And reply to this message");

casper.then(function () {
    // TODO: test correct events have fired
    // Test opening the compose box from the left side buttons
    casper.click('body');
    casper.page.sendEvent('keypress', "c");
    casper.test.assertVisible('#compose', 'Compose box appears after clicking side stream button');
    casper.test.assertVisible('#stream', 'Stream input box visible');
    common.check_form('#send_message_form', {stream: '', subject: ''}, "Stream empty on new compose");
    casper.click('body');
    casper.page.sendEvent('keypress', "C");
    casper.test.assertVisible('#private_message_recipient', 'Switching from stream compose to PM compose');
    common.check_form('#send_message_form', {recipient: ''}, "Recipient empty on new PM");
    casper.click('body');
    casper.page.sendEvent('keypress', 'c');
    casper.test.assertVisible('#stream', 'Switching from PM compose to stream compose');
    common.check_form('#send_message_form', {stream: '', subject: ''}, "Stream empty on new compose");

    // Check that when you reply to a message it pre-populates the stream and subject fields
    casper.click('body');
    casper.clickLabel("We reply to this message");
    casper.test.assertVisible('#stream', 'Stream input box visible on reply');
    common.check_form('#send_message_form', {stream: "Verona", subject: "Reply test"}, "Stream populated after reply by click");
    // Or recipient field
    casper.click('body');
    casper.clickLabel("And reply to this message");
    common.check_form('#send_message_form', {recipient: "cordelia@humbughq.com"}, "Recipient populated after PM click");

    common.keypress(27); //escape
    casper.page.sendEvent('keypress', 'k');
    casper.page.sendEvent('keypress', 'r');
    common.check_form('#send_message_form', {stream: "Verona", subject: "Reply test"}, "Stream populated after reply with `r`");

    // Test "closing" the compose box
    casper.click('body');
});

casper.waitWhileVisible('#stream');
casper.then(function () {
    casper.test.assertNotVisible('#stream', 'Close stream compose box');
    casper.page.sendEvent('keypress', "C");
    casper.click('body');
});

casper.waitWhileVisible('#private-message');
casper.then(function () {
    casper.test.assertNotVisible('#private-message', 'Close PM compose box');
});

common.then_log_out();

casper.run(function () {
    casper.test.done(17);
});
