casper = require("casper").create verbose: true

countLinks = ->
    document.querySelectorAll('a').length

suites = [
    ->
        @echo "Suite 1"
        @start "http://google.com/", -> @echo "Page title: #{@getTitle()}"
        @then -> @echo "#{@evaluate(countLinks)} links"
    ->
        @echo "Suite 2"
        @start "http://yahoo.com/", -> @echo "Page title: #{@getTitle()}"
        @then -> @echo "#{@evaluate(countLinks)} links"
    ->
        @echo "Suite 3"
        @start "http://bing.com/", -> @echo "Page title: #{@getTitle()}"
        @then -> @echo "#{@evaluate(countLinks)} links"
]

casper.start()

casper.then ->
    @echo("Starting")

currentSuite = 0;

check = ->
    if suites[currentSuite]
        suites[currentSuite].call @
        currentSuite++;
        casper.run check
    else
        @echo "All done."
        @exit()

casper.run check
