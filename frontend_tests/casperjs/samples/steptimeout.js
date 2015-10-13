/*jshint strict:false*/
/*global CasperError console phantom require*/

var failed = [];
var start = null;
var links = [
    "http://google.com/'",
    "http://akei.com/'",
    "http://lemonde.fr/'",
    "http://liberation.fr/'",
    "http://cdiscount.fr/"
];

var casper = require("casper").create({
    onStepTimeout: function() {
        failed.push(this.requestUrl);
        this.test.fail(this.requestUrl + " loads in less than " + timeout + "ms.");
    }
});

casper.on("load.finished", function() {
    this.echo(this.requestUrl + " loaded in " + (new Date() - start) + "ms", "PARAMETER");
});

var timeout = ~~casper.cli.get(0);
casper.options.stepTimeout = timeout > 0 ? timeout : 1000;

casper.echo("Testing with timeout=" + casper.options.stepTimeout + "ms, please be patient.");

casper.start();

casper.each(links, function(casper, link) {
    this.then(function() {
        this.test.comment("Loading " + link);
        start = new Date();
        this.open(link);
    });
    this.then(function() {
        var message = this.requestUrl + " loads in less than " + timeout + "ms.";
        if (failed.indexOf(this.requestUrl) === -1) {
            this.test.pass(message);
        }
    });
});

casper.run(function() {
    this.test.renderResults(true);
});
