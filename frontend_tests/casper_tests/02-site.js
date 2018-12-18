/* Script for testing the web client.

   This runs under CasperJS.  It's an end-to-end black-box sort of test.  It
   simulates clicking around in the app, sending messages, etc.  We run against
   a real development server instance and avoid mocking as much as possible.
*/

// Provides a few utility functions.
// See http://casperjs.org/api.html#utils
// For example, utils.dump() prints an Object with nice formatting.
var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Sanity-checking existing messages');

    var msg = common.get_rendered_messages('zhome');

    msg.headings.forEach(function (heading) {
        casper.test.assertMatch(common.normalize_spaces(heading),
                                /(^You and )|( )/,
                                'Heading is well-formed');
    });

    casper.test.info('Sending messages');
});

// Send some messages.

common.then_send_many([
    { stream: 'Verona', subject: 'frontend test',
      content: 'test verona A' },

    { stream: 'Verona', subject: 'frontend test',
      content: 'test verona B' },

    { stream: 'Verona', subject: 'other subject',
      content: 'test verona C' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content: 'personal A' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content: 'personal B' },

    { recipient: 'cordelia@zulip.com',
      content: 'personal C' }]);

common.wait_for_receive(function () {
    common.expected_messages('zhome', [
        'Verona > frontend test',
        'Verona > other subject',
        'You and Cordelia Lear, King Hamlet',
        'You and Cordelia Lear',
    ], [
        '<p>test verona A</p>',
        '<p>test verona B</p>',
        '<p>test verona C</p>',
        '<p>personal A</p>',
        '<p>personal B</p>',
        '<p>personal C</p>',
    ]);

    casper.test.info('Sending more messages');
});

common.then_send_many([
    { stream: 'Verona', subject: 'frontend test',
      content: 'test verona D' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content: 'personal D' },
]);

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
