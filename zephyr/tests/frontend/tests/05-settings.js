var common = require('../common.js').common;

common.start_and_log_in();

casper.then(function() {
    casper.test.info('Settings page');
    casper.click('a[href^="#settings"]');
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/#settings/, 'URL suggests we are on settings page');
    casper.test.assertExists('#settings.tab-pane.active', 'Settings page is active');
});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});
