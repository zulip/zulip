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

casper.waitForText("And reply to this message", function () {
    // TODO: Test opening the compose box from the left side buttons
    casper.click('body');
    casper.page.sendEvent('keypress', "c");
});

casper.waitUntilVisible('#compose', function () {
    casper.test.assertVisible('#stream', 'Stream input box visible');
    common.check_form('#send_message_form', {stream: '', subject: ''}, "Stream empty on new compose");
    casper.click('body');
    casper.page.sendEvent('keypress', "C");
});

casper.waitUntilVisible('#private_message_recipient', function () {
    common.check_form('#send_message_form', {recipient: ''}, "Recipient empty on new PM");
    casper.click('body');
    casper.page.sendEvent('keypress', 'c');
});

casper.waitUntilVisible('#stream', function () {
    common.check_form('#send_message_form', {stream: '', subject: ''}, "Stream empty on new compose");

    // Check that when you reply to a message it pre-populates the stream and subject fields
    casper.click('body');
    casper.clickLabel("We reply to this message");
});

casper.waitUntilVisible('#stream', function () {
    common.check_form('#send_message_form', {stream: "Verona", subject: "Reply test"}, "Stream populated after reply by click");
    // Or recipient field
    casper.click('body');
    casper.clickLabel("And reply to this message");
});

casper.waitUntilVisible('#private_message_recipient', function () {
    common.check_form('#send_message_form', {recipient: "cordelia@humbughq.com"}, "Recipient populated after PM click");

    common.keypress(27); //escape
    casper.page.sendEvent('keypress', 'k');
    casper.page.sendEvent('keypress', 'r');
});

casper.waitUntilVisible('#stream', function () {
    common.check_form('#send_message_form', {stream: "Verona", subject: "Reply test"}, "Stream populated after reply with `r`");

    // Test "closing" the compose box
    casper.click('body');
});

casper.waitWhileVisible('#stream', function () {
    casper.test.assertNotVisible('#stream', 'Close stream compose box');
    casper.page.sendEvent('keypress', "C");
    casper.click('body');
});

casper.waitWhileVisible('#private-message', function () {
    casper.test.assertNotVisible('#private-message', 'Close PM compose box');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
