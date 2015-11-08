/*jshint strict:false*/
/*global CasperError console phantom require*/

/**
 * This script will add a custom HTTP status code handler, here for 404 pages.
 */
var casper = require("casper").create();

casper.on("http.status.200", function(resource) {
    this.echo(resource.url + " is OK", "INFO");
});

casper.on("http.status.301", function(resource) {
    this.echo(resource.url + " is permanently redirected", "PARAMETER");
});

casper.on("http.status.302", function(resource) {
    this.echo(resource.url + " is temporarily redirected", "PARAMETER");
});

casper.on("http.status.404", function(resource) {
    this.echo(resource.url + " is not found", "COMMENT");
});

casper.on("http.status.500", function(resource) {
    this.echo(resource.url + " is in error", "ERROR");
});

var links = [
    "http://google.com/",
    "http://www.google.com/",
    "http://www.google.com/plop"
];

casper.start();

casper.each(links, function(self, link) {
    self.thenOpen(link, function() {
        this.echo(link + " loaded");
    });
});

casper.run();
