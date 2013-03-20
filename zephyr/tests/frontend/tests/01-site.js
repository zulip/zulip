/* Script for testing the web client.

   This runs under CasperJS.  It's an end-to-end black-box sort of test.  It
   simulates clicking around in the app, sending messages, etc.  We run against
   a real development server instance and avoid mocking as much as possible.
*/

// Provides a few utility functions.
// See http://casperjs.org/api.html#utils
// For example, utils.dump() prints an Object with nice formatting.
var utils = require('utils');

var common = require('../common.js').common;

// Uncomment this to get page-context console.log in the CasperJS output
// (plus some CasperJS-specific messages)
/*
casper.on('remote.message', function (msg) {
    casper.echo(msg);
});
*/

function un_narrow() {
    casper.test.info('Un-narrowing');
    common.keypress(27); // Esc
}

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Sanity-checking existing messages');

    var msg = common.get_rendered_messages('zhome');

    msg.headings.forEach(function (heading) {
        casper.test.assertMatch(common.normalize_spaces(heading),
            /(^You and )|( > )/,
            'Heading is well-formed');
    });

    msg.bodies.forEach(function (body) {
        casper.test.assertMatch(body,
            /^(<p>(.|\n)*<\/p>)?$/,
            'Body is well-formed');
    });

    casper.test.info('Sending messages');
});

common.wait_and_send('stream', {
    stream:  'Verona',
    subject: 'frontend test',
    content: 'test message A'
});

common.wait_and_send('stream', {
    stream:  'Verona',
    subject: 'frontend test',
    content: 'test message B'
});

common.wait_and_send('stream', {
    stream:  'Verona',
    subject: 'other subject',
    content: 'test message C'
});

common.wait_and_send('private', {
    recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
    content:   'personal A'
});

common.wait_and_send('private', {
    recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
    content:   'personal B'
});

common.wait_and_send('private', {
    recipient: 'cordelia@humbughq.com',
    content:   'personal C'
});

common.wait_for_receive(function () {
    common.expected_messages('zhome', [
        'Verona > frontend test',
        'Verona > other subject',
        'You and Cordelia Lear, King Hamlet',
        'You and Cordelia Lear'
    ], [
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>test message C</p>',
        '<p>personal A</p>',
        '<p>personal B</p>',
        '<p>personal C</p>'
    ]);

    casper.test.info('Sending more messages');

    common.send_message('stream', {
        stream:  'Verona',
        subject: 'frontend test',
        content: 'test message D'
    });
});

common.wait_and_send('private', {
    recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
    content:   'personal D'
});

common.wait_for_receive(function () {
    casper.test.info('Narrowing to stream');
    casper.click('*[title="Narrow to stream \\\"Verona\\\""]');
});

casper.then(function () {
    common.expected_messages('zfilt', [
        'Verona > frontend test',
        'Verona > other subject',
        'Verona > frontend test'
    ], [
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>test message C</p>',
        '<p>test message D</p>'
    ]);

    un_narrow();
});

casper.then(function () {
    common.expected_messages('zhome', [
        'Verona > frontend test',
        'You and Cordelia Lear, King Hamlet'
    ], [
        '<p>test message D</p>',
        '<p>personal D</p>'
    ]);

    casper.test.info('Narrowing to subject');
    casper.click('*[title="Narrow to stream \\\"Verona\\\", subject \\\"frontend test\\\""]');
});

casper.then(function () {
    common.expected_messages('zfilt', [
        'Verona > frontend test'
    ], [
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>test message D</p>'
    ]);

    un_narrow();
});

casper.then(function () {
    casper.test.info('Narrowing to personals');
    casper.click('*[title="Narrow to your private messages with Cordelia Lear, King Hamlet"]');
});

casper.then(function () {
    common.expected_messages('zfilt', [
        'You and Cordelia Lear, King Hamlet'
    ], [
        '<p>personal A</p>',
        '<p>personal B</p>',
        '<p>personal D</p>'
    ]);
});

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
