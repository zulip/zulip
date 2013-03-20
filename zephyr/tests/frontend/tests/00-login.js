var common = require('../common.js').common;

// Start of test script.
casper.start('http://localhost:9981/', common.initialize_casper);

casper.then(function () {
    casper.test.assertHttpStatus(302);
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/accounts\/home/, 'Redirected to /accounts/home');
    casper.click('a[href^="/accounts/login"]');
});

common.then_log_in();

casper.then(function () {
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
