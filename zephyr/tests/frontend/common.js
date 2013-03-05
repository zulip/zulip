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

function log_in(credentials) {
    if (credentials === undefined) {
        credentials = {username: 'iago@humbughq.com', password: 'FlokrWdZefyEWkfI'};
    }

    casper.test.info('Logging in');
    casper.fill('form[action^="/accounts/login"]', {
        username: credentials.username,
        password: credentials.password
    }, true /* submit form */);
}

exports.then_log_in = function (credentials) {
    casper.then(function () {
        log_in(credentials);
    });
};

exports.start_and_log_in = function (credentials, viewport) {
    viewport = viewport || {width: 1280, height: 768};
    casper.start('http://localhost:9981/accounts/login', function () {
        // Fail if we get a JavaScript error in the page's context.
        // Based on the example at http://phantomjs.org/release-1.5.html
        //
        // casper.on('error') doesn't work (it never gets called) so we
        // set this at the PhantomJS level.  We do it inside 'start' so
        // that we know we have a page object.
        casper.page.onError = function (msg, trace) {
            casper.test.error(msg);
            casper.echo('Traceback:');
            trace.forEach(function (item) {
                casper.echo('  ' + item.file + ':' + item.line);
            });
            casper.exit(1);
        };
        casper.page.viewportSize = viewport;

        log_in(credentials);
    });
};

exports.then_log_out = function () {
    casper.then(function () {
        casper.test.info('Logging out');
        casper.click('li[title="Log out"] a');
    });
};

exports.send_message = function (type, params) {
    casper.waitForSelector('#left_bar_compose_' + type + '_button_big', function () {
        casper.click('#left_bar_compose_' + type + '_button_big');
        casper.fill('form[action^="/json/send_message"]', params);
        casper.click('#compose-send-button');
        casper.waitWhileVisible('#compose');
    });
};

// Wait for any previous send to finish, then send a message.
exports.wait_and_send = function (type, params) {
    casper.waitForSelector('#compose-send-button:enabled', function () {
        exports.send_message(type, params);
    });
};


return exports;

}());

// For inclusion with CasperJS
try {
    exports.common = common;
} catch (e) {
}
