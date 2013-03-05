/*global casper*/
/*jshint strict:false*/
casper.test.comment('Casper.start()');

casper.start('tests/site/index.html', function() {
    this.test.pass('Casper.start() can chain a next step');
    this.test.assertTitle('CasperJS test index', 'Casper.start() opened the passed url');
    this.test.assertEval(function() {
        return typeof(__utils__) === "object";
    }, 'Casper.start() injects ClientUtils instance within remote DOM');
});

casper.test.assert(casper.started, 'Casper.start() started');

casper.run(function() {
    this.test.done(4);
});
