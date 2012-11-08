/*global casper*/
/*jshint strict:false*/
// skip this test for phantom versions < 1.5
if (phantom.version.major === 1 && phantom.version.minor < 6) {
    casper.test.comment('Skipped tests, PhantomJS 1.6 required');
    casper.test.done();
} else {
    casper.setFilter('page.prompt', function(message, value) {
        return 'Chuck ' + value;
    });

    casper.start('tests/site/prompt.html', function() {
        this.test.assertEquals(this.getGlobal('name'), 'Chuck Norris', 'prompted value has been received');
    });

    casper.run(function() {
        this.test.done();
    });
}
