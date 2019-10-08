var common = require('../casper_lib/common.js').common;
var realm_url = "http://zulip.zulipdev.com:9981/";

// Start of test script.
common.init_viewport();
casper.start(realm_url, common.initialize_casper);

casper.then(function () {
    casper.test.assertUrlMatch(/^http:\/\/[^/]+\/login\/$/, 'Redirected to /login/');
});

common.then_log_in();

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
