/*global casper*/
/*jshint strict:false*/
/**
 * Special test server to test for HTTP status codes
 *
 */
var server = require('webserver').create();
var service = server.listen(8090, function (request, response) {
    var code = parseInt(/^\/(\d+)$/.exec(request.url)[1], 10);
    response.statusCode = code;
    response.write("");
    response.close();
});
var fs = require("fs");

casper.start();

// file protocol
casper.thenOpen('file://' + phantom.casperPath + '/tests/site/index.html', function() {
    this.test.assertHttpStatus(null, 'file:// protocol does not set a HTTP status');
});

// http protocol
var codes = [100, 101, 102, 118, 200, 201, 202, 203, 204, 205, 206, 207, 210,
         300, 301, 302, 303, 304, 305, 307, 310,
         400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413,
              414, 415, 416, 417, 418, 422, 423, 424, 425, 426, 449, 450,
         500, 501, 502, 503, 504, 505, 507, 509];

casper.each(codes, function(self, code) {
    if (code === 100) {
        // HTTP 100 is CONTINUE, so don't expect a terminated response
        return;
    }
    this.thenOpen('http://localhost:8090/' + code, function() {
        this.test.assertEquals(this.currentHTTPStatus, code);
        this.test.assertHttpStatus(code);
    });
});

casper.run(function() {
    server.close();
    this.test.done(109);
});
