var common = require('../casper_lib/common.js').common;
var REALMS_HAVE_SUBDOMAINS = casper.cli.get('subdomains');

var realm_url = "";
if (REALMS_HAVE_SUBDOMAINS) {
    realm_url = "http://zulip.zulipdev.com:9981/";
} else {
    realm_url = "http://localhost:9981/";
}
// Start of test script.
common.init_viewport();
casper.start(realm_url, common.initialize_casper);

casper.then(function () {
    casper.test.assertUrlMatch(/^http:\/\/[^/]+\/login/, 'Redirected to /login');
});

common.then_log_in();

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});
