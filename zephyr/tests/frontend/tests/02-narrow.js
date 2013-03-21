var common = require('../common.js').common;

function un_narrow() {
    casper.test.info('Un-narrowing');
    common.keypress(27); // Esc
}

common.start_and_log_in();

// We could use the messages sent by 01-site.js, but we want to
// make sure each test file can be run individually (which the
// 'run' script provides for).

casper.then(function () {
    casper.test.info('Sending messages');
});

common.send_many([
    { stream:  'Verona', subject: 'frontend test',
      content: 'test message A' },

    { stream:  'Verona', subject: 'frontend test',
      content: 'test message B' },

    { stream:  'Verona', subject: 'other subject',
      content: 'test message C' },

    { recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
      content:   'personal A' },

    { recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
      content:   'personal B' },

    { recipient: 'cordelia@humbughq.com',
      content:   'personal C' },

    { stream:  'Verona', subject: 'frontend test',
      content: 'test message D' },

    { recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
      content:   'personal D' }
]);


// Narrow by clicking links.

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
