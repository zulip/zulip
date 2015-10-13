###
This script will add a custom HTTP status code handler, here for 404 pages.
###

casper = require("casper").create()

casper.on "http.status.200", (resource) ->
    @echo "#{resource.url} is OK", "INFO"

casper.on "http.status.301", (resource) ->
    @echo "#{resource.url} is permanently redirected", "PARAMETER"

casper.on "http.status.302", (resource) ->
    @echo "#{resource.url} is temporarily redirected", "PARAMETER"

casper.on "http.status.404", (resource) ->
    @echo "#{resource.url} is not found", "COMMENT"

casper.on "http.status.500", (resource) ->
    @echo "#{resource.url} is in error", "ERROR"

links = [
    "http://google.com/"
    "http://www.google.com/"
    "http://www.google.com/plop"
]

casper.start()

casper.each links, (self, link) ->
    self.thenOpen link, ->
        @echo "#{link} loaded"

casper.run()
