/*
 * This script will capture a screenshot of a twitter account page
 * Usage: $ casperjs screenshot.coffee <twitter-account> <filename.[jpg|png|pdf]>
 */

var casper = require("casper").create({
    viewportSize: {
        width: 1024,
        height: 768
    }
});

var twitterAccount = casper.cli.get(0);
var filename       = casper.cli.get(1);

if (!twitterAccount || !filename || !/\.(png|jpg|pdf)$/i.test(filename)) {
    casper
        .echo("Usage: $ casperjs screenshot.coffee <twitter-account> <filename.[jpg|png|pdf]>")
        .exit(1)
    ;
}

casper.start("https://twitter.com/#!/" + twitterAccount, function() {
    this.waitForSelector(".tweet-row", (function() {
        this.captureSelector(filename, "html");
        this.echo("Saved screenshot of " + (this.getCurrentUrl()) + " to " + filename);
    }), (function() {
        this.die("Timeout reached. Fail whale?");
        this.exit();
    }), 12000);
});

casper.run();
