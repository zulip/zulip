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
casper.waitForText('Subscribed', function () {
    casper.test.assertTextExists('Subscribed', 'Initial subscriptions loaded');
    casper.fill('form#add_new_subscription', {stream_name: 'Announcement'});
    casper.click('form#add_new_subscription input.btn');
});
casper.waitForText('Announcement', function () {
    casper.test.assertTextExists('Create stream Announcement', 'Modal for specifying new stream users');
    casper.click('form#stream_creation_form button.btn.btn-primary');
});

casper.waitFor(function () {
    return casper.evaluate(function () {
        return $('.subscription_name').is(':contains("Announcement")');
    });
});

casper.then(function () {
    casper.test.info('Narrowing to stream zulip');
    casper.click('a[href^="#narrow/stream/zulip"]');
});


casper.then(function () {
    casper.test.assertSelectorHasText('title', 'zulip - Zulip Dev - Zulip', 'Narrowed to stream zulip');
    casper.test.assertTextExists('just created', "Stream Announcement exists");
    this.clickLabel('Unsubscribe from announcement', 'button');
});

casper.waitForText('Subscribe to announcement', function () {
    casper.test.assertTextExists('Subscribe to announcement', "Unsubscribed from Announcement");
    this.clickLabel('Subscribe to announcement', 'button');
});

casper.waitForText('Unsubscribe from announcement', function () {
    casper.test.assertTextExists('Unsubscribe from announcement', "Subscribed to Announcement");
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
