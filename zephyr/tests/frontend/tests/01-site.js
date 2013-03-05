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

// Get message headings (recipient rows) and bodies out of the DOM.
// casper.evaluate plays weird tricks with a closure, evaluating
// it in the web page's context.  Passing arguments from the test
// script's context is awkward (c.f. the various appearances of
// 'table' here).
function get_rendered_messages(table) {
    return casper.evaluate(function (table) {
        var tbl = $('#'+table);
        return {
            headings: $.map(tbl.find('.recipient_row .right_part'), function (elem) {
                return elem.innerText;
            }),

            bodies: $.map(tbl.find('.message_content'), function (elem) {
                return elem.innerHTML;
            })
        };
    }, {
        table: table
    });
}

// Inject key presses by running some jQuery code in page context.
// If we upgrade to CasperJS 1.0 and PhantomJS 1.7+, we can do this
// in a more straightforward way.
function keypress(code) {
    casper.evaluate(function (code) {
        $('body').trigger($.Event('keydown', { which: code }));
    }, {
        code: code
    });
}

function timestamp() {
    return new Date().getTime();
}

// The timestamp of the last message send or get_updates result.
var last_send_or_update = -1;

// Update that variable whenever get_updates returns.
casper.on('resource.received', function (resource) {
    if (/\/json\/get_updates/.test(resource.url)) {
        last_send_or_update = timestamp();
    }
});

// Send a Humbug message.
function send_message(type, params) {
    last_send_or_update = timestamp();

    casper.click('#left_bar_compose_' + type + '_button_big');
    casper.fill('form[action^="/json/send_message"]', params);
    casper.click('#compose-send-button');
}

// Wait for any previous send to finish, then send a message.
function wait_and_send(type, params) {
    casper.waitForSelector('#compose-send-button:enabled', function () {
        send_message(type, params);
    });
}

// Wait to receive queued messages.
function wait_for_receive(step) {
    // Wait until the last send or get_updates result was more than 300 ms ago.
    casper.waitFor(function () {
        return (timestamp() - last_send_or_update) > 300;
    }, step);
}

// innerText sometimes gives us non-breaking space characters, and occasionally
// a different number of spaces than we expect.
function normalize_spaces(str) {
    return str.replace(/\s+/g, ' ');
}

// Call get_rendered_messages and then check that the last few headings and
// bodies match the specified arrays.
function expected_messages(table, headings, bodies) {
    casper.test.assertVisible('#'+table,
        table + ' is visible');

    var msg = get_rendered_messages(table);

    casper.test.assertEquals(
        msg.headings.slice(-headings.length).map(normalize_spaces),
        headings,
        'Got expected message headings');

    casper.test.assertEquals(
        msg.bodies.slice(-bodies.length),
        bodies,
        'Got expected message bodies');
}

function un_narrow() {
    casper.test.info('Un-narrowing');
    keypress(27); // Esc
}

common.log_in();

casper.then(function () {
    casper.test.info('Sanity-checking existing messages');

    var msg = get_rendered_messages('zhome');

    msg.headings.forEach(function (heading) {
        casper.test.assertMatch(normalize_spaces(heading),
            /(^You and )|( > )/,
            'Heading is well-formed');
    });

    msg.bodies.forEach(function (body) {
        casper.test.assertMatch(body,
            /^(<p>(.|\n)*<\/p>)?$/,
            'Body is well-formed');
    });

    casper.test.info('Disabling tutorial, if present');
    send_message('private', {
        recipient: 'humbug+tutorial@humbughq.com',
        content: 'exit'
    });

    casper.test.info('Sending messages');
});

wait_and_send('stream', {
    stream:  'Verona',
    subject: 'frontend test',
    content: 'test message A'
});

wait_and_send('stream', {
    stream:  'Verona',
    subject: 'frontend test',
    content: 'test message B'
});

wait_and_send('stream', {
    stream:  'Verona',
    subject: 'other subject',
    content: 'test message C'
});

wait_and_send('private', {
    recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
    content:   'personal A'
});

wait_and_send('private', {
    recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
    content:   'personal B'
});

wait_and_send('private', {
    recipient: 'cordelia@humbughq.com',
    content:   'personal C'
});

wait_for_receive(function () {
    expected_messages('zhome', [
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

    send_message('stream', {
        stream:  'Verona',
        subject: 'frontend test',
        content: 'test message D'
    });
});

wait_and_send('private', {
    recipient: 'cordelia@humbughq.com, hamlet@humbughq.com',
    content:   'personal D'
});

wait_for_receive(function () {
    casper.test.info('Narrowing to stream');
    casper.click('*[title="Narrow to stream \\\"Verona\\\""]');
});

casper.then(function () {
    expected_messages('zfilt', [
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
    expected_messages('zhome', [
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
    expected_messages('zfilt', [
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
    expected_messages('zfilt', [
        'You and Cordelia Lear, King Hamlet'
    ], [
        '<p>personal A</p>',
        '<p>personal B</p>',
        '<p>personal D</p>'
    ]);
});

// Subscriptions page tests
casper.then(function() {
    casper.test.info('Subscriptions page');
    casper.click('a[href^="#subscriptions"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#subscriptions/, 'URL suggests we are on subscriptions page');
    casper.test.assertExists('#subscriptions.tab-pane.active', 'Subscriptions page is active');
    // subscriptions need to load; if they have *any* subs,
    // the word "Unsubscribe" will appear
    casper.waitForText('Unsubscribe');
});
casper.then(function() {
    casper.test.assertTextExists('Unsubscribe', 'Initial subscriptions loaded');
    casper.fill('form#add_new_subscription', {stream_name: 'Waseemio'});
    casper.click('form#add_new_subscription input.btn.btn-primary');
    casper.waitForText('Waseemio');
});
casper.then(function() {
    casper.test.assertTextExists('Create stream Waseemio', 'Modal for specifying new stream users');
    casper.click('form#stream_creation_form button.btn.btn-primary');
    casper.waitFor(function () {
        return casper.evaluate(function () {
            return $('.subscription_name').is(':contains("Waseemio")');
        });
    });
});
casper.then(function() {
    casper.test.assertSelectorHasText('.subscription_name', 'Waseemio', 'Subscribing to a stream');
    casper.fill('form#add_new_subscription', {stream_name: 'WASeemio'});
    casper.click('form#add_new_subscription input.btn.btn-primary');
    casper.waitForText('Already subscribed');
});
casper.then(function() {
    casper.test.assertTextExists('Already subscribed', "Can't subscribe twice to a stream");
    casper.fill('form#add_new_subscription', {stream_name: '  '});
    casper.click('form#add_new_subscription input.btn.btn-primary');
    casper.waitForText('Error adding subscription');
});
casper.then(function() {
    casper.test.assertTextExists('Error adding subscription', "Can't subscribe to an empty stream name");
});

// Settings page tests
casper.then(function() {
    casper.test.info('Settings page');
    casper.click('a[href^="#settings"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#settings/, 'URL suggests we are on settings page');
    casper.test.assertExists('#settings.tab-pane.active', 'Settings page is active');
});


common.log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
