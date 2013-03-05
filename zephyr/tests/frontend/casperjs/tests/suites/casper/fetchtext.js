/*global casper*/
/*jshint strict:false*/
casper.test.comment('Casper.fetchText()');

casper.start('tests/site/index.html', function() {
    this.test.assertEquals(this.fetchText('ul li'), 'onetwothree', 'Casper.fetchText() can retrieve text contents');
});

casper.run(function() {
    this.test.done(1);
});
