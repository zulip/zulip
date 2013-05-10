var common = require('../common.js').common;

function star_count() {
    return casper.evaluate(function () {
        return $("#zhome .icon-vector-star").length;
    });
}

function toggle_last_star() {
    casper.evaluate(function () {
        $("#zhome .star").last().click();
    });
}

common.start_and_log_in();

casper.then(function() {
    casper.test.info("Sending test message");
    common.send_message('stream', {
        stream:  'Verona',
        subject: 'stars',
        content: 'test star'
    });
    casper.waitForText("test star");
});

casper.then(function() {
    casper.test.info("Checking star counts");

    // Initially, no messages are starred.
    casper.test.assertEquals(star_count(), 0,
                             "Got expected empty star count.");

    // Clicking on a message star stars it.
    toggle_last_star();
    casper.test.assertEquals(star_count(), 1,
                             "Got expected single star count.");

    casper.click('a[href^="#narrow/is/starred"]');
});

casper.then(function() {
    // You can narrow to your starred messages.
    common.expected_messages('zfilt', ['Verona stars'], ['<p>test star</p>']);
    common.un_narrow();
});

casper.then(function() {
    // Clicking on a starred message unstars it.
    toggle_last_star();
    casper.test.assertEquals(star_count(), 0,
                             "Got expected re-empty star count.");
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
