casper = require("casper").create()

links = [
    "http://google.com/"
    "http://yahoo.com/"
    "http://bing.com/"
]

casper.start()

casper.each links, (self, link) ->
    @thenOpen link, -> @echo "#{@getTitle()} - #{link}"

casper.run()
