var common = require('../casper_lib/common.js').common;

function count() {
    return casper.evaluate(function () {
        return $("#zhome").length;
    });
}
function unread_count() {
    return casper.evaluate(function () {
        return $("#zhome .icon-vector-unread:not(.read)").length;
    });
}

function toggle_last_unread() {
    casper.evaluate(function () {
        $("#zhome .unread").last().click();
    });
}

var num_messages = count();

common.start_and_log_in();

casper.then(function () {
    casper.test.info("Sending test message");
});

common.then_send_message('stream', {
        stream:  'Verona',
        subject: 'unread',
        content: 'test unread',
});

casper.waitForText("test unread");

casper.then(function () {
    casper.test.info("Checking unread counts");

    // Initially, all messages are unread.
    casper.test.assertEquals(unread_count(), count(),
                             "Got expected full unread count.");

    // Clicking on a message (or its unread icon) makes it read.
    toggle_last_unread();
    casper.test.assertEquals(unread_count(), count() - 1,
                             "Got expected almost full unread count.");

    casper.click('a[href^="#narrow/is/unread"]');
});

casper.waitUntilVisible('#zfilt', function () {
    // You can narrow to your unread messages.
    common.expected_messages('zfilt', ['Verona > unread'], ['<p>test unread</p>']);
    common.un_narrow();
});

casper.then(function () {
    // Clicking on a read message's unread icon makes it read.
    toggle_last_unread();
    casper.test.assertEquals(unread_count(), count(),
                             "Got expected re-full unread count.");
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
