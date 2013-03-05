/*global casper*/
/*jshint strict:false*/
// Dear curious test reader,
// The on* family of methods is considered deprecated since 0.6.0; please use events instead

// Casper.options.onStepComplete
casper.start('tests/site/index.html', function() {
    this.options.onStepComplete = function(self, stepResult) {
        this.test.comment('Casper.options.onStepComplete()');
        this.test.assertEquals(stepResult, 'ok', 'Casper.options.onStepComplete() is called on step complete');
        self.options.onStepComplete = null;
    };
    return 'ok';
});

// Casper.options.onResourceRequested & Casper.options.onResourceReceived
casper.then(function() {
    this.options.onResourceReceived = function(self, resource) {
        this.test.comment('Casper.options.onResourceReceived()');
        this.test.assertType(resource, 'object', 'Casper.options.onResourceReceived() retrieve a resource object');
        this.test.assert('status' in resource, 'Casper.options.onResourceReceived() retrieve a valid resource object');
        self.options.onResourceReceived = null;
    };
    this.options.onResourceRequested = function(self, request) {
        this.test.comment('Casper.options.onResourceRequested()');
        this.test.assertType(request, 'object', 'Casper.options.onResourceRequested() retrieve a request object');
        this.test.assert('method' in request, 'Casper.options.onResourceRequested() retrieve a valid request object');
        self.options.onResourceRequested = null;
    };
    this.thenOpen('tests/site/page1.html');
});

// Casper.options.onAlert()
casper.then(function() {
    this.options.onAlert = function(self, message) {
        self.test.assertEquals(message, 'plop', 'Casper.options.onAlert() can intercept an alert message');
    };
});

casper.run(function() {
    this.options.onAlert = null;
    this.test.done(5);
});
