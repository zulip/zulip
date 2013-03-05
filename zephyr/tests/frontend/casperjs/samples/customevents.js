/*jshint strict:false*/
/*global CasperError console phantom require*/

var casper = require("casper").create();

// listening to a custom event
casper.on("google.loaded", function(title) {
    this.echo("Google page title is " + title);
});

casper.start("http://google.com/", function() {
    // emitting a custom event
    this.emit("google.loaded", this.getTitle());
});

casper.run();
