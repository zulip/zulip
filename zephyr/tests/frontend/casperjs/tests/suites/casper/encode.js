/*global casper*/
/*jshint strict:false*/
var fs = require('fs');

// FIXME: we're using local url scheme until https://github.com/ariya/phantomjs/pull/288 is
// possibly merged
casper.start('file://' + phantom.casperPath + '/tests/site/index.html', function() {
    var imageUrl = 'file://' + phantom.casperPath + '/tests/site/images/phantom.png';
    var image = this.base64encode(imageUrl);

    this.test.comment('Casper.base64encode()');
    this.test.assertEquals(image.length, 6160, 'Casper.base64encode() can retrieve base64 contents');

    this.test.comment('Casper.download()');
    this.download(imageUrl, '__test_logo.png');
    this.test.assert(fs.exists('__test_logo.png'), 'Casper.download() downloads a file');
    if (fs.exists('__test_logo.png')) {
        fs.remove('__test_logo.png');
    }
});

casper.run(function() {
    this.test.done(2);
});
