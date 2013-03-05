/*global casper*/
/*jshint strict:false*/
function testUA(ua, match) {
    casper.test.assertMatch(
        ua, match, 'Default user agent matches ' + match
    );
}

function fetchUA(request) {
    testUA(request.headers.filter(function(header) {
        return header.name === "User-Agent";
    }).pop().value, /plop/);
}

testUA(casper.options.pageSettings.userAgent, /CasperJS/);

casper.start();

casper.userAgent('plop').on('resource.requested', fetchUA);

casper.thenOpen('tests/site/index.html');

casper.run(function() {
    this.removeListener('resource.requested', fetchUA);
    this.test.done(3);
});
