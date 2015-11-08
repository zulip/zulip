var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

// Send a message to try replying to
common.then_send_many([
    { stream: 'Verona',
      subject: 'Reply test',
      content: "We reply to this message"
    },
    { recipient: "cordelia@zulip.com",
      content: "And reply to this message"
    }
]);

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
});

casper.waitWhileVisible('#stream', function () {
    casper.clickLabel("We reply to this message");
});

casper.waitUntilVisible('#stream', function () {
    common.check_form('#send_message_form', {stream: "Verona", subject: "Reply test"}, "Stream populated after reply by click");
    // Or recipient field
    casper.click('body');
    casper.clickLabel("And reply to this message");
});

casper.waitUntilVisible('#private_message_recipient', function () {
    common.check_form('#send_message_form', {recipient: "cordelia@zulip.com"}, "Recipient populated after PM click");

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

// Test focus after narrowing to PMs with a user and typing 'c'
casper.then(function () {
    casper.click('*[title="Narrow to your private messages with Cordelia Lear"]');
});
casper.waitUntilVisible('#tab_list li.private_message', function () {
    casper.page.sendEvent('keypress', 'c');
});
casper.waitUntilVisible('#compose', function () {
    casper.test.assertEval(function () {
        return document.activeElement === $('#stream')[0];
    }, 'Stream box focused after narrowing to PMs with a user and pressing `c`');
});

// Make sure multiple PM recipients display properly.
var recipients = ['cordelia@zulip.com', 'othello@zulip.com'];
casper.then(function () {
    common.keypress(27);  // escape to dismiss compose box
});
casper.waitWhileVisible('.message_comp');
common.then_send_many([
    { recipient: recipients.join(','),
      content:   'A huddle to check spaces' }]);

casper.then(function () {
    common.keypress(27);  // escape to dismiss compose box
});
casper.then(function () {
    common.un_narrow();
});
casper.waitUntilVisible('#zhome', function () {
    casper.clickLabel('A huddle to check spaces');
});
casper.waitUntilVisible('#compose', function () {
    // It may be possible to get the textbox contents with CasperJS,
    // but it's easier to just evaluate jQuery in page context here.
    var displayed_recipients = casper.evaluate(function () {
        return $('#private_message_recipient').val();
    });
    casper.test.assertEquals(displayed_recipients, recipients.join(', '),
        'Recipients are displayed correctly in a huddle reply');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
