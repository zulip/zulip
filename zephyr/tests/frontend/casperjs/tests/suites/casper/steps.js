/*global casper*/
/*jshint strict:false*/
casper.test.comment('Casper.then()');

casper.start('tests/site/index.html');

var nsteps = casper.steps.length;

casper.then(function(response) {
    this.test.assertTitle('CasperJS test index', 'Casper.then() added a new step');
});

casper.test.assertEquals(casper.steps.length, nsteps + 1, 'Casper.then() can add a new step');

casper.test.comment('Casper.thenOpen()');

casper.thenOpen('tests/site/test.html');

casper.test.assertEquals(casper.steps.length, nsteps + 2, 'Casper.thenOpen() can add a new step');

casper.thenOpen('tests/site/test.html', function() {
    this.test.assertTitle('CasperJS test target', 'Casper.thenOpen() opened a location and executed a step');
});

casper.test.assertEquals(casper.steps.length, nsteps + 4, 'Casper.thenOpen() can add a new step for opening, plus another step');

casper.test.comment('Casper.each()');
casper.each([1, 2, 3], function(self, item, i) {
    self.test.assertEquals(i, item - 1, 'Casper.each() passes a contextualized index');
});

casper.run(function() {
    this.test.done(8);
});
