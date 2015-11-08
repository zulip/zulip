/*jshint strict:false*/
/*global CasperError console phantom require*/

var casper = require("casper").create();
var dump = require("utils").dump;

// removing default options passed by the Python executable
casper.cli.drop("cli");
casper.cli.drop("casper-path");

if (casper.cli.args.length === 0 && Object.keys(casper.cli.options).length === 0) {
    casper
        .echo("Pass some args and options to see how they are handled by CasperJS")
        .exit(1)
    ;
}

casper.echo("Casper CLI passed args:");
dump(casper.cli.args);

casper.echo("Casper CLI passed options:");
dump(casper.cli.options);

casper.exit();
