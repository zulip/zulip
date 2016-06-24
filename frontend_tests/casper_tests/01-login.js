var common = require('../casper_lib/common.js').common;

// Start of test script.
casper.start('http://localhost:9981/', common.initialize_casper);

casper.then(function () {
    casper.test.assertHttpStatus(302);
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/login/, 'Redirected to /login');
});

common.then_log_in();

casper.waitForSelector('#zhome', function () {
    casper.test.info('Logging out');
    casper.click('li[title="Log out"] a');
});

casper.then(function () {
    casper.test.assertHttpStatus(200);
    casper.test.assertUrlMatch(/accounts\/login\/$/);
});

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
