/*global casper*/
/*jshint strict:false*/
casper.options.remoteScripts = [
    'includes/include1.js', // local includes are actually served
    'includes/include2.js', // through the local test webserver
    'http://code.jquery.com/jquery-1.8.3.min.js'
];

casper.start('tests/site/index.html', function() {
    this.test.assertSelectorHasText('#include1', 'include1',
        'Casper.includeRemoteScripts() includes a first remote script on start');
    this.test.assertSelectorHasText('#include2', 'include2',
        'Casper.includeRemoteScripts() includes a second remote script on start');
    this.test.assertEval(function() {
        return 'jQuery' in window;
    }, 'Casper.includeRemoteScripts() includes a really remote file on first step');
});

casper.thenOpen('tests/site/form.html', function() {
    this.test.assertSelectorHasText('#include1', 'include1',
        'Casper.includeRemoteScripts() includes a first remote script on second step');
    this.test.assertSelectorHasText('#include2', 'include2',
        'Casper.includeRemoteScripts() includes a second remote script on second step');
    this.test.assertEval(function() {
        return 'jQuery' in window;
    }, 'Casper.includeRemoteScripts() includes a really remote file on second step');
});

casper.run(function() {
    this.options.remoteScripts = [];
    this.test.done(6);
});
