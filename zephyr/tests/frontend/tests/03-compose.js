var common = require('../common.js').common;

common.log_in();

casper.then(function () {
    // TODO: test correct events have fired
    // Test opening the compose box from the left side buttons
    casper.click('#left_bar_compose_stream_button_big');
    casper.test.assertVisible('#compose', 'Compose box appears after clicking side stream button');
    casper.test.assertVisible('#stream', 'Stream input box visible');
    casper.click('#left_bar_compose_private_button_big');
    casper.test.assertVisible('#private_message_recipient', 'Switching from stream compose to PM compose');
    casper.click('#left_bar_compose_stream_button_big');
    casper.test.assertVisible('#stream', 'Switching from PM compose to stream compose');

    // Test closing the compose box
    casper.click('.composebox-close');
});

casper.waitWhileVisible('#compose');
casper.then(function () {
    casper.test.assertNotVisible('#compose', 'Close stream compose box');
    casper.click('#left_bar_compose_private_button_big');
    casper.click('.composebox-close');
});

casper.waitWhileVisible('#compose');
casper.then(function () {
    casper.test.assertNotVisible('#compose', 'Close PM compose box');
});

common.log_out();

casper.run(function () {
    casper.test.done(6);
});