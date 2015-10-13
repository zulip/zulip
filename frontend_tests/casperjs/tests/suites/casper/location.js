/*jshint strict:false*/
/*global CasperError casper console phantom require*/
var utils = require('utils')

if (utils.ltVersion(phantom.version, '1.8.0')) {
    // https://github.com/n1k0/casperjs/issues/101
    casper.warn('document.location is broken under phantomjs < 1.8');
    casper.test.done();
} else {
    casper.start('tests/site/index.html', function() {
        this.evaluate(function() {
            document.location = '/tests/site/form.html';
        });
    });

    casper.then(function() {
        this.test.assertUrlMatches(/form\.html$/);
    });

    casper.run(function() {
        this.test.done();
    });
}
