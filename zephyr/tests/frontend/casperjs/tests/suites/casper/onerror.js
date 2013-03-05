/*global casper*/
/*jshint strict:false*/
casper.test.comment("page.error event");

var error = {};

casper.start();

casper.on("page.error", function onError(msg, trace) {
    error.msg = msg;
    error.trace = trace;
});

casper.thenOpen('tests/site/error.html', function() {
    this.test.assertEquals(error.msg, "ReferenceError: Can't find variable: plop", 'page.error event has been caught OK');
    this.test.assertMatch(error.trace[0].file, /error.html/, 'page.error retrieves correct stack trace');
});

casper.run(function() {
    this.test.done(2);
});
