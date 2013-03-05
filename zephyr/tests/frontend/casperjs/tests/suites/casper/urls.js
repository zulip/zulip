/*global casper*/
/*jshint strict:false*/
casper.start('tests/site/urls.html', function() {
    this.clickLabel('raw unicode', 'a');
}).then(function() {
    this.test.assertHttpStatus(200);
    this.test.assertUrlMatches('Forlì', 'Casper.getCurrentUrl() retrieves a raw unicode URL');
    this.clickLabel('escaped', 'a');
});

casper.then(function() {
    this.test.assertHttpStatus(200);
    this.test.assertUrlMatches('Forlì', 'Casper.getCurrentUrl() retrieves an escaped URL');
    this.clickLabel('uri encoded', 'a');
});

casper.run(function() {
    this.test.assertHttpStatus(200);
    this.test.assertUrlMatches('Forlì', 'Casper.getCurrentUrl() retrieves a decoded URL');
    this.test.done(6);
});
