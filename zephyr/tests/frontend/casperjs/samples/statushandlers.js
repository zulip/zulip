/*jshint strict:false*/
/*global CasperError console phantom require*/

/**
 * This script will add a custom HTTP status code handler, here for 404 pages.
 */

var casper = require("casper").create({
    httpStatusHandlers: {
        404: function(self, resource) {
            this.echo("Resource at " + resource.url + " not found (404)", "COMMENT");
        }
    },
    verbose: true
});

casper.start("http://www.google.com/plop", function() {
    this.echo("Done.");
    this.exit();
});

casper.run();
