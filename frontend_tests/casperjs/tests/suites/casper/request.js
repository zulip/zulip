/*global casper*/
/*jshint strict:false*/
function testHeader(header) {
    return header.name === 'Accept' && header.value === 'application/json';
}

var t = casper.test, current = 0, tests = [
    function(request) {
        t.assertNot(request.headers.some(testHeader), "Casper.open() sets no custom header by default");
    },
    function(request) {
        t.assert(request.headers.some(testHeader), "Casper.open() can set a custom header");
    },
    function(request) {
        t.assertNot(request.headers.some(testHeader), "Casper.open() custom headers option is not persistent");
    }
];

casper.on('page.resource.requested', function(request) {
    tests[current++](request);
});

casper.start();

casper.thenOpen('tests/site/index.html');
casper.thenOpen('tests/site/index.html', {
    headers: {
        Accept: 'application/json'
    }
});
casper.thenOpen('tests/site/index.html');

casper.run(function() {
    this.removeAllListeners('page.resource.requested');
    t.done(3);
});
