/*global casper*/
/*jshint strict:false*/
casper.start('tests/site/page1.html');
casper.thenOpen('tests/site/page2.html');
casper.thenOpen('tests/site/page3.html');

casper.back();
casper.then(function() {
    this.test.comment('navigating history backward');
    this.test.assertMatch(this.getCurrentUrl(), /tests\/site\/page2\.html$/, 'Casper.back() can go back an history step');
});

casper.forward();
casper.then(function() {
    this.test.comment('navigating history forward');
    this.test.assertMatch(this.getCurrentUrl(), /tests\/site\/page3\.html$/, 'Casper.forward() can go forward an history step');
});

casper.run(function() {
    this.test.assert(this.history.length > 0, 'Casper.history contains urls');
    this.test.assertMatch(this.history[0], /tests\/site\/page1\.html$/, 'Casper.history has the correct first url');
    this.test.done(4);
});
