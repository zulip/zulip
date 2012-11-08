/*global casper*/
/*jshint strict:false*/
// skip this test for phantom versions < 1.5
if (phantom.version.major === 1 && phantom.version.minor < 6) {
    casper.test.comment('Skipped tests, PhantomJS 1.6 required');
    casper.test.done();
} else {
    var received;

    casper.setFilter('page.confirm', function(message) {
        received = message;
        return true;
    });

    casper.start('tests/site/confirm.html', function() {
        this.test.assert(this.getGlobal('confirmed'), 'confirmation received');
    });

    casper.run(function() {
        this.test.assertEquals(received, 'are you sure?', 'confirmation message is ok');
        this.test.done();
    });
}
