/*global casper*/
/*jshint strict:false maxstatements:99*/

casper.start('tests/site/index.html');

casper.configureHttpAuth('http://localhost/');
casper.test.assertEquals(casper.page.settings.userName, undefined);
casper.test.assertEquals(casper.page.settings.password, undefined);

casper.configureHttpAuth('http://niko:plop@localhost/');
casper.test.assertEquals(casper.page.settings.userName, 'niko');
casper.test.assertEquals(casper.page.settings.password, 'plop');

casper.configureHttpAuth('http://localhost/', {username: 'john', password: 'doe'});
casper.test.assertEquals(casper.page.settings.userName, 'john');
casper.test.assertEquals(casper.page.settings.password, 'doe');

casper.configureHttpAuth('http://niko:plop@localhost/', {username: 'john', password: 'doe'});
casper.test.assertEquals(casper.page.settings.userName, 'niko');
casper.test.assertEquals(casper.page.settings.password, 'plop');

casper.run(function() {
    this.test.done(8);
});
