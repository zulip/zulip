/*global casper*/
/*jshint strict:false*/
casper.test.comment('Casper.exists()');

casper.start('tests/site/index.html', function() {
    this.test.assert(this.exists('a') && !this.exists('chucknorriz'), 'Casper.exists() can check if an element exists');
});

casper.run(function() {
    this.test.done(1);
});
