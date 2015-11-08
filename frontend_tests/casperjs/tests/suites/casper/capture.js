/*global casper*/
/*jshint strict:false*/
var fs = require('fs'), testFile = '/tmp/__casper_test_capture.png';

if (fs.exists(testFile) && fs.isFile(testFile)) {
    fs.remove(testFile);
}

casper.start('tests/site/index.html', function() {
    this.viewport(300, 200);
    this.test.comment('Casper.capture()');
    this.capture(testFile);
    this.test.assert(fs.isFile(testFile), 'Casper.capture() captured a screenshot');
});

casper.thenOpen('tests/site/index.html', function() {
    this.test.comment('Casper.captureBase64()');
    this.test.assert(this.captureBase64('png').length > 0,
                     'Casper.captureBase64() rendered a page capture as base64');
    this.test.assert(this.captureBase64('png', 'ul').length > 0,
                     'Casper.captureBase64() rendered a capture from a selector as base64');
    this.test.assert(this.captureBase64('png', {top: 0, left: 0, width: 30, height: 30}).length > 0,
                     'Casper.captureBase64() rendered a capture from a clipRect as base64');
});

casper.run(function() {
    try {
        fs.remove(testFile);
    } catch(e) {}
    this.test.done(4);
});
