/*global casper*/
/*jshint strict:false*/
casper.test.comment('Casper.headers.get()');

var server = require('webserver').create();
var service = server.listen(8090, function(request, response) {
    response.statusCode = 200;
    response.headers = {
        'Content-Language': 'en',
        'Content-Type': 'text/html',
        'Date': new Date().toUTCString()
    };
    response.write("ok");
    response.close();
});

function dumpHeaders() {
    casper.test.comment('Dumping current response headers');

    casper.currentResponse.headers.forEach(function(header) {
        casper.test.comment('- ' + header.name + ': ' + header.value);
    });
}

// local file:// url
casper.start('file://' + phantom.casperPath + 'tests/site/index.html', function thenLocalPage(response) {
    this.test.assertEquals(response, undefined, 'No response available on local page');
});

casper.thenOpen('http://localhost:8090/', function thenLocalhost(response) {
    var headers = response.headers;

    this.test.assertEquals(headers.get('Content-Language'), 'en', 'Checking existing header (case sensitive)');
    this.test.assertEquals(headers.get('content-language'), 'en', 'Checking existing header (case insensitive)');
    this.test.assertEquals(headers.get('X-Is-Troll'), null, 'Checking unexisting header');
});

casper.run(function() {
    server.close();
    this.test.done(4);
});
