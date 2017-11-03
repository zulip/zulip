/* Script for testing muting on the web client.
*/

// Provides a few utility functions.
// See http://casperjs.org/api.html#utils
// For example, utils.dump() prints an Object with nice formatting.
var utils = require('utils');

var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Sending messages');
});

// Send some messages:
// first, one that we expect to never be muted (the left bracket)
// then, two topics that we'll mute
// and then, another topic that we expect to never be muted (right bracket).

common.then_send_many([
    { stream:  'Verona', subject: 'mute test left bracket',
      content: 'left bracket test message A' },

    { stream:  'Verona', subject: 'mute test',
      content: 'test message A' },

    { stream:  'Verona', subject: 'mute test',
      content: 'test message B' },

    { stream:  'Verona', subject: 'mute test 2',
      content: 'test message C' },

    { stream:  'Verona', subject: 'mute test right bracket',
      content: 'right bracket test message C' }]);

common.wait_for_receive(function () {
    common.expected_messages('zhome', [
        'Verona > mute test left bracket',
        'Verona > mute test',
        'Verona > mute test 2',
        'Verona > mute test right bracket'
    ], [
        '<p>left bracket test message A</p>',
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>test message C</p>',
        '<p>right bracket test message C</p>'
    ]);

    common.un_narrow();
});

// Catch up to the last message:
casper.then(function () {
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.info').click();
        $('.popover_edit_message').click();
    });
    common.un_narrow();
});

casper.then(function () {
    casper.test.info('Muting messages');
    casper.page.sendEvent('keypress', 'k');
    casper.page.sendEvent('keypress', 'M');
    casper.page.sendEvent('keypress', 'k');
    casper.page.sendEvent('keypress', 'M');

    casper.test.info('First mute command sent, waiting...');
});

casper.waitForSelector('.topic_muted', function () {
        common.expected_messages('zhome', [
            'Verona > mute test left bracket',
            'Verona > mute test right bracket'
    ], [
        '<p>left bracket test message A</p>',
        '<p>right bracket test message C</p>'
    ]);
    casper.test.info('Message list is correct - unmuting via the button...');
    casper.evaluate(function () {
        var unmute_btn = $('#topic_muted .topic_muted:last .topic_unmute_link');
        unmute_btn.click();
    });
});

// The first muted topic should have been unmuted:
common.wait_for_receive(function () {
    common.expected_messages('zhome', [
        'Verona > mute test left bracket',
        'Verona > mute test',
        'Verona > mute test right bracket'
    ], [
        '<p>left bracket test message A</p>',
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>right bracket test message C</p>'
    ]);
    casper.test.info('First unmute successful, now unmuting via key bindings...');
});

casper.thenClick('#stream_filters [data-name="Verona"]  a', function () {
    casper.thenClick('#stream_filters [data-name="Verona"] ul.expanded_subjects .muted_topic a', function () {
        common.keypress(27); // Escape to deactivate the message edit box
        casper.page.sendEvent('keypress', 'U');
        common.un_narrow();
    });
});

// This should have restored our entire previous state:
casper.waitUntilVisible('#zhome', function () {
    common.expected_messages('zhome', [
        'Verona > mute test left bracket',
        'Verona > mute test',
        'Verona > mute test 2',
        'Verona > mute test right bracket'
    ], [
        '<p>left bracket test message A</p>',
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>test message C</p>',
        '<p>right bracket test message C</p>'
    ]);
});

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
