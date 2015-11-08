casper = require("casper").create()
url = casper.cli.get 0
metas = []

if not url
    casper
        .echo("Usage: $ casperjs metaextract.coffee <url>")
        .exit 1

casper.start url, ->
    metas = @evaluate ->
        metas = []
        castarray = (arr) -> [].slice.call(arr)
        for elem in castarray document.querySelectorAll "meta"
            meta = {}
            for attr in castarray elem.attributes
                meta[attr.name] = attr.value
            metas.push meta
        metas

casper.run ->
    require("utils").dump metas
    this.exit()
