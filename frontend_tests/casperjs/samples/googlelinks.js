/*jshint strict:false*/
/*global CasperError console phantom require*/
var links = [];
var casper = require("casper").create();

function getLinks() {
    var links = document.querySelectorAll("h3.r a");
    return Array.prototype.map.call(links, function(e) {
        try {
            // google handles redirects hrefs to some script of theirs
            return (/url\?q=(.*)&sa=U/).exec(e.getAttribute("href"))[1];
        } catch (err) {
            return e.getAttribute("href");
        }
    });
}

casper.start("http://google.fr/", function() {
    // search for 'casperjs' from google form
    this.fill('form[action="/search"]', { q: "casperjs" }, true);
});

casper.then(function() {
    // aggregate results for the 'casperjs' search
    links = this.evaluate(getLinks);
    // now search for 'phantomjs' by fillin the form again
    this.fill('form[action="/search"]', { q: "phantomjs" }, true);
});

casper.then(function() {
    // aggregate results for the 'phantomjs' search
    links = links.concat(this.evaluate(getLinks));
});

casper.run(function() {
    // echo results in some pretty fashion
    this.echo(links.length + " links found:");
    this.echo(" - " + links.join("\n - "));
    this.exit();
});
