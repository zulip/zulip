/*jshint strict:false*/
/*global CasperError console phantom require*/

/**
 * download the google logo image onto the local filesystem
 */

var casper = require("casper").create();

casper.start("http://www.google.fr/", function() {
    this.download("http://www.google.fr/images/srpr/logo3w.png", "logo.png");
});

casper.run();
