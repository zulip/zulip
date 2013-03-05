/*global casper*/
/*jshint strict:false*/
casper.start('tests/site/index.html', function() {
    this.test.assertEquals(this.getHTML('ul li'), 'one', 'Casper.getHTML() retrieves inner HTML by default');
    this.test.assertEquals(this.getHTML('ul li', true), '<li>one</li>', 'Casper.getHTML() can retrieve outer HTML');
});

casper.run(function() {
    casper.test.done(2);
});
