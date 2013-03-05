/*jshint strict:false*/
/*global CasperError casper console phantom require*/
casper.start('about:blank', function() {
    this.test.pass('ok1');
});

casper.then(function() {
    this.test.pass('ok2');
});

casper.run(function() {
    this.test.pass('ok3');
    this.test.done();
});
