var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Subscriptions page');
    casper.click('a[href^="#subscriptions"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#subscriptions/, 'URL suggests we are on subscriptions page');
    casper.test.assertExists('#subscriptions.tab-pane.active', 'Subscriptions page is active');
    // subscriptions need to load; if they have *any* subs,
    // the word "Unsubscribe" will appear
});
casper.waitForSelector('.sub_unsub_button.subscribed-button', function () {
    casper.test.assertTextExists('Subscribed', 'Initial subscriptions loaded');
    casper.click('form#add_new_subscription input.btn');
});
casper.waitForText('Create stream', function () {
    casper.test.assertTextExists('Create stream', 'Modal for specifying new stream users');
    casper.fill('form#stream_creation_form', {stream_name: 'Waseemio'});
    casper.click('form#stream_creation_form button.btn.btn-primary');
});

casper.waitFor(function () {
    return casper.evaluate(function () {
        return $('.subscription_name').is(':contains("Waseemio")');
    });
});

casper.then(function () {
    casper.test.assertSelectorHasText('.subscription_name', 'Waseemio', 'Subscribing to a stream');
    casper.click('form#add_new_subscription input.btn');
});
casper.waitForText('Create stream', function () {
    casper.test.assertTextExists('Create stream', 'Modal for specifying new stream users');
    casper.fill('form#stream_creation_form', {stream_name: 'WASeemio'});
    casper.click('form#stream_creation_form button.btn.btn-primary');
});
casper.waitForText('Already subscribed', function () {
    casper.test.assertTextExists('Already subscribed', "Can't subscribe twice to a stream");
    casper.click('form#add_new_subscription input.btn');
});
casper.waitForText('Create stream', function () {
    casper.test.assertTextExists('Create stream', 'Modal for specifying new stream users');
    casper.fill('form#stream_creation_form', {stream_name: '  '});
    casper.click('form#stream_creation_form button.btn.btn-primary');
});
casper.waitForText('Error adding subscription', function () {
    casper.test.assertTextExists('Error adding subscription', "Can't subscribe to an empty stream name");
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
