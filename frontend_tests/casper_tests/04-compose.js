var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

var msgs_qty;

casper.then(function () {
    casper.waitUntilVisible("#zhome");
});

casper.then(function () {
    msgs_qty = this.evaluate(function () {
        return $('#zhome .message_row').length;
    });
});

// Send a message to try replying to
common.then_send_many([
    { stream: 'Verona',
      subject: 'Reply test',
      content: "We reply to this message",
    },
    { recipient: "cordelia@zulip.com",
      content: "And reply to this message",
    },
]);

casper.then(function () {
    casper.waitFor(function check_length() {
        return casper.evaluate(function (expected_length) {
            return $('#zhome .message_row').length === expected_length;
        }, msgs_qty + 2);
    });
});

casper.then(function () {
    // TODO: Test opening the compose box from the left side buttons
    casper.click('body');
    casper.page.sendEvent('keypress', "c");
});

casper.then(function () {
    casper.waitUntilVisible('#compose', function () {
        casper.test.assertVisible('#stream-message', 'Stream input box visible');
        common.check_form('#send_message_form', {stream: '', subject: ''}, "Stream empty on new compose");
        casper.click('body');
        casper.page.sendEvent('keypress', "x");
    });
});

casper.then(function () {
    casper.waitUntilVisible('#private_message_recipient', function () {
        common.pm_recipient.expect("");
        casper.click('body');
        casper.page.sendEvent('keypress', 'c');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#stream-message', function () {
        common.check_form('#send_message_form', {stream: '', subject: ''}, "Stream empty on new compose");

        // Check that when you reply to a message it pre-populates the stream and subject fields
        casper.click('body');
    });
});

casper.then(function () {
    casper.waitWhileVisible('#stream-message', function () {
        casper.clickLabel("We reply to this message");
    });
});

casper.then(function () {
    casper.waitUntilVisible('#stream-message', function () {
        common.check_form('#send_message_form', {stream: "Verona", subject: "Reply test"}, "Stream populated after reply by click");
        // Or recipient field
        casper.click('body');
        casper.clickLabel("And reply to this message");
    });
});

casper.then(function () {
    casper.waitUntilVisible('#private_message_recipient', function () {
        common.pm_recipient.expect("cordelia@zulip.com");

        common.keypress(27); //escape
        casper.page.sendEvent('keypress', 'k');
        casper.page.sendEvent('keypress', 'r');
    });
});

casper.then(function () {
    casper.waitUntilVisible('#stream-message', function () {
        common.check_form('#send_message_form', {stream: "Verona", subject: "Reply test"}, "Stream populated after reply with `r`");

        // Test "closing" the compose box
        casper.click('body');
    });
});

casper.then(function () {
    casper.waitWhileVisible('#stream-message', function () {
        casper.test.assertNotVisible('#stream-message', 'Close stream compose box');
        casper.page.sendEvent('keypress', "x");
        casper.click('body');
    });
});

casper.then(function () {
    casper.waitWhileVisible('#private-message', function () {
        casper.test.assertNotVisible('#private-message', 'Close PM compose box');
    });
});

// Test focus after narrowing to PMs with a user and typing 'c'
casper.then(function () {
    casper.click('*[title="Narrow to your private messages with Cordelia Lear"]');
});
casper.waitUntilVisible('#tab_list li.private_message', function () {
    casper.page.sendEvent('keypress', 'c');
});

casper.then(function () {
    casper.waitUntilVisible('#compose', function () {
        casper.test.assertEval(function () {
            return document.activeElement === $('.compose_table #stream')[0];
        }, 'Stream box focused after narrowing to PMs with a user and pressing `c`');
    });
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

casper.then(function () {
    casper.waitUntilVisible('#compose', function () {
        common.pm_recipient.expect(recipients.join(','));
    });
});

casper.then(function () {
    casper.waitUntilVisible('#markdown_preview', function () {
        casper.test.assertNotVisible('#undo_markdown_preview', 'Write button is hidden');
        casper.click("#markdown_preview");
    });
});

casper.then(function () {
    casper.waitWhileVisible("#markdown_preview", function () {
        casper.test.assertVisible('#undo_markdown_preview', 'Write button is visible');
        casper.test.assertEquals(casper.getHTML('#preview_content'), "Nothing to preview", "Nothing to preview");
        casper.click("#undo_markdown_preview");
    });
});

casper.then(function () {
    casper.waitWhileVisible("#undo_markdown_preview", function () {
        casper.test.assertVisible('#markdown_preview', 'Preview button is visible.');
        casper.test.assertNotVisible('#undo_markdown_preview', 'Write button is hidden.');
        casper.test.assertEquals(casper.getHTML('#preview_content'), "", "Markdown preview area is empty");

        casper.fill('form[action^="/json/messages"]', {
            content: '**Markdown Preview** >> Test for markdown preview',
        }, false);

        casper.click("#markdown_preview");
    });
});

casper.then(function () {
    casper.waitForSelectorTextChange("#preview_content", function () {
        casper.test.assertEquals(casper.getHTML('#preview_content'), "<p><strong>Markdown Preview</strong> &gt;&gt; Test for markdown preview</p>", "Check markdown is previewed properly");
    });
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
