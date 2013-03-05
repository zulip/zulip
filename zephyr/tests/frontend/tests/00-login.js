// Start of test script.
casper.start('http://localhost:9981/', function () {
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

    casper.test.assertHttpStatus(302);
    casper.test.assertUrlMatch(/^http:\/\/[^\/]+\/accounts\/home/, 'Redirected to /accounts/home');
    casper.click('a[href^="/accounts/login"]');
});

// casper.then will perform the action after the effects of previous clicks etc. are finished.
casper.then(function () {
    casper.test.info('Logging in');
    casper.fill('form[action^="/accounts/login"]', {
        username: 'iago@humbughq.com',
        password: 'FlokrWdZefyEWkfI'
    }, true /* submit form */);
});

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
