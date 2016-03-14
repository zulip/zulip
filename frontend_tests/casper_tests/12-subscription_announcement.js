var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Narrowing to stream notifications');
    // this.debugHTML();
    casper.click('a[href^="#narrow/stream/notifications"]');
});


casper.then(function(){
	casper.test.assertSelectorHasText('title', 'notifications - Zulip Dev - Zulip', 'Narrowed to stream notifications');
	casper.test.assertTextExists('Bot created', "Stream Announcement exists");
	this.clickLabel('Subscribe to announcement', 'button');
});

casper.waitForText('Unsubscribe from announcement', function(){
    // this.clickLabel('Subscribe to waseemio', 'button');
    casper.test.assertTextExists('Unsubscribe from announcement', "Subscribed to Announcement");
    this.clickLabel('Unsubscribe from announcement', 'button');
    // this.debugHTML();
});

casper.waitForText('Subscribe to announcement', function(){
    // this.clickLabel('Subscribe to waseemio', 'button');
    casper.test.assertTextExists('Subscribe to announcement', "Unsubscribed from Announcement");
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});