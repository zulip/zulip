casper = require("casper").create
    loadImages: false
    logLevel:   "debug"
    verbose:    true

links =
    "http://edition.cnn.com/": 0
    "http://www.nytimes.com/": 0
    "http://www.bbc.co.uk/": 0
    "http://www.guardian.co.uk/": 0

fantomas = Object.create(casper)

fantomas.countLinks = ->
    @evaluate ->
        __utils__.findAll("a[href]").length

fantomas.renderJSON = (what) ->
    @echo JSON.stringify(what, null, "  ")

fantomas.start()

Object.keys(links).forEach (url) ->
    fantomas.thenOpen url, ->
        links[url] = @countLinks()

fantomas.run ->
    @renderJSON(links)
    @exit()
