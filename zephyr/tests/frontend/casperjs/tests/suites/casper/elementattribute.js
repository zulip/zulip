/*global casper*/
/*jshint strict:false*/
casper.start('tests/site/elementattribute.html', function() {
    this.test.comment('Casper.getElementAttribute()');
    this.test.assertEquals(this.getElementAttribute('.testo','data-stuff'), 'beautiful string', 'Casper.getElementAttribute() works as intended');
});

casper.run(function() {
    this.test.done(1);
});
