var common = require('../common.js').common;

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Subscriptions page');
    casper.click('a[href^="#subscriptions"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#subscriptions/, 'URL suggests we are on subscriptions page');
    casper.test.assertExists('#subscriptions.tab-pane.active', 'Subscriptions page is active');
    // subscriptions need to load; if they have *any* subs,
    // the word "Unsubscribe" will appear
    casper.waitForText('Subscribed');
});
casper.then(function () {
    casper.test.assertTextExists('Subscribed', 'Initial subscriptions loaded');
    casper.fill('form#add_new_subscription', {stream_name: 'Waseemio'});
    casper.click('form#add_new_subscription input.zulip-button');
    casper.waitForText('Waseemio');
});
casper.then(function () {
    casper.test.assertTextExists('Create stream Waseemio', 'Modal for specifying new stream users');
    casper.click('form#stream_creation_form button.btn.btn-primary');
    casper.waitFor(function () {
        return casper.evaluate(function () {
            return $('.subscription_name').is(':contains("Waseemio")');
        });
    });
});
casper.then(function () {
    casper.test.assertSelectorHasText('.subscription_name', 'Waseemio', 'Subscribing to a stream');
    casper.fill('form#add_new_subscription', {stream_name: 'WASeemio'});
    casper.click('form#add_new_subscription input.zulip-button');
    casper.waitForText('Already subscribed');
});
casper.then(function () {
    casper.test.assertTextExists('Already subscribed', "Can't subscribe twice to a stream");
    casper.fill('form#add_new_subscription', {stream_name: '  '});
    casper.click('form#add_new_subscription input.zulip-button');
    casper.waitForText('Error adding subscription');
});
casper.then(function () {
    casper.test.assertTextExists('Error adding subscription', "Can't subscribe to an empty stream name");
});

// Test the inline subscribe and unsubscribe in messages
casper.then(function () {
    casper.click('a[href^="#"]');
    casper.test.assertExists('#home.tab-pane.active', 'home page is active');
});

// Test an inline subscribe button for an unsubscribed stream
common.send_message('stream', {
    stream: 'Verona',
    subject: 'Inline subscribe',
    content: "!_stream_subscribe_button(inline stream)"
});

var new_stream_button = '.inline-subscribe[data-stream-name="inline stream"] .inline-subscribe-button';

casper.waitUntilVisible(new_stream_button, function () {
    casper.test.assertSelectorHasText(new_stream_button,
                                      'Subscribe to inline stream',
                                      'New inline subscribe button starts as subscribe');
    casper.click(new_stream_button);
});

casper.waitUntilVisible('.narrow-filter[data-name="inline stream"]', function () {
    casper.test.assertSelectorHasText(new_stream_button,
                                      'Unsubscribe from inline stream',
                                      'New inline subscribe button becomes unsubscribe');
    casper.click(new_stream_button);
});

casper.waitWhileVisible('.narrow-filter[data-name="inline stream"]', function () {
    casper.test.assertSelectorHasText(new_stream_button,
                                      'Subscribe to inline stream',
                                      'New inline subscribe returns to subscribe on unsubscribe');
});

// Test an inline subscribe button for an subscribed stream
common.send_message('stream', {
    stream: 'Verona',
    subject: 'Inline subscribe',
    content: "!_stream_subscribe_button(Denmark)"
});

var existing_stream_button = '.inline-subscribe[data-stream-name="Denmark"] .inline-subscribe-button';

casper.waitUntilVisible(new_stream_button, function () {
    casper.test.assertSelectorHasText(existing_stream_button,
                                      'Unsubscribe from denmark',
                                      'Existing subscribe button starts as unsubscribe');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
