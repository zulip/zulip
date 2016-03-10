var common = require('../casper_lib/common.js').common;
var test_credentials_secondary = require('../casper_lib/test_credentials_secondary.js').test_credentials_secondary;

common.start_and_log_in(test_credentials_secondary);
casper.then(function () {
        casper.test.info('Settings page');
        casper.click('a[href^="#"]');
        casper.test.assertTextExists('Subscribe to waseemio', "Home Page for hamlet loaded");
        this.clickLabel('Subscribe to waseemio', 'button');
});
 casper.waitForText('Unsubscribe from waseemio', function () {
    casper.test.assertTextExists('Unsubscribe from waseemio', "Subsribed to waseemio, now testing Unsubscribe");
    this.clickLabel('Unsubscribe from waseemio', 'button');
});
casper.waitForText('Subscribe to waseemio', function () {
        casper.test.assertTextExists('Subscribe to waseemio', "Unsubscribed from waseemio");      
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
