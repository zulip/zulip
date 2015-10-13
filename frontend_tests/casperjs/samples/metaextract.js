/*jshint strict:false*/
/*global CasperError console phantom require*/

var casper = require("casper").create();
var url = casper.cli.get(0);
var metas = [];

if (!url) {
    casper
        .echo("Usage: $ casperjs metaextract.js <url>")
        .exit(1)
    ;
}

casper.start(url, function() {
    metas = this.evaluate(function() {
        var metas = [];
        [].forEach.call(document.querySelectorAll("meta"), function(elem) {
            var meta = {};
            [].slice.call(elem.attributes).forEach(function(attr) {
                meta[attr.name] = attr.value;
            });
            metas.push(meta);
        });
        return metas;
    });
});

casper.run(function() {
    require("utils").dump(metas);
    this.exit();
});
