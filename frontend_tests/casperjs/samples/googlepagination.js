/*jshint strict:false*/
/*global CasperError console phantom require*/

/**
 * Capture multiple pages of google search results
 *
 * Usage: $ casperjs googlepagination.coffee my search terms
 *
 * (all arguments will be used as the query)
 */

var casper = require("casper").create();
var currentPage = 1;

if (casper.cli.args.length === 0) {
    casper
        .echo("Usage: $ casperjs googlepagination.js my search terms")
        .exit(1)
    ;
}

var processPage = function() {
    var url;
    this.echo("capturing page " + currentPage);
    this.capture("google-results-p" + currentPage + ".png");

    // don't go too far down the rabbit hole
    if (currentPage >= 5) {
        return;
    }

    if (this.exists("#pnnext")) {
        currentPage++;
        this.echo("requesting next page: " + currentPage);
        url = this.getCurrentUrl();
        this.thenClick("#pnnext").then(function() {
            this.waitFor(function() {
                return url !== this.getCurrentUrl();
            }, processPage);
        });
    } else {
        this.echo("that's all, folks.");
    }
};

casper.start("http://google.fr/", function() {
    this.fill('form[action="/search"]', {
        q: casper.cli.args.join(" ")
    }, true);
});

casper.then(processPage);

casper.run();
