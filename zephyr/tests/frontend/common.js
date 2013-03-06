// Set default viewport size to something reasonable
casper.page.viewportSize = {width: 1280, height: 768 };

// Fail if we get a JavaScript error in the page's context.
// Based on the example at http://phantomjs.org/release-1.5.html
//
// casper.on('error') doesn't work (it never gets called) so we
// set this at the PhantomJS level.
casper.page.onError = function (msg, trace) {
    casper.test.error(msg);
    casper.echo('Traceback:');
    trace.forEach(function (item) {
        casper.echo('  ' + item.file + ':' + item.line);
    });
    casper.exit(1);
};

// Capture screens from all failures
var casper_failure_count = 1;
casper.test.on('fail', function failure() {
    if (casper_failure_count <= 10) {
        casper.capture("/tmp/casper-failure" + casper_failure_count + ".png");
        casper_failure_count++;
    }
});

var common = (function () {

var exports = {};

exports.log_in = function () {
    casper.start('http://localhost:9981/accounts/login');

    casper.then(function () {
        casper.test.info('Logging in');
        casper.fill('form[action^="/accounts/login"]', {
            username: 'iago@humbughq.com',
            password: 'FlokrWdZefyEWkfI'
        }, true /* submit form */);
    });
};

exports.log_out = function () {
    casper.then(function () {
        casper.test.info('Logging out');
        casper.click('li[title="Log out"] a');
    });
};

return exports;

}());

// For inclusion with CasperJS
try {
    exports.common = common;
} catch (e) {
}