casper = require("casper").create
    verbose: true

# The base links array
links = [
    "http://google.com/"
    "http://yahoo.com/"
    "http://bing.com/"
]

currentLink = 0;

# If we don't set a limit, it could go on forever
upTo = ~~casper.cli.get(0) || 10

###
Get the links, and add them to the links array
(It could be done all in one step, but it is intentionally splitted)
###
addLinks = (link) ->
    @then ->
        found = @evaluate searchLinks
        @echo "#{found.length} links found on #{link}"
        links = links.concat found

###
Fetch all <a> elements from the page and return
the ones which contains a href starting with 'http://'
###
searchLinks = ->
    filter = Array::filter
    map = Array::map
    map.call filter.call(document.querySelectorAll("a"), (a) ->
        (/^http:\/\/.*/i).test a.getAttribute("href")
    ), (a) ->
        a.getAttribute "href"

# Just opens the page and prints the title
start = (link) ->
    @start link, ->
        @echo "Page title: #{ @getTitle() }"

# As long as it has a next link, and is under the maximum limit, will keep running
check = ->
    if links[currentLink] && currentLink < upTo
        @echo "--- Link #{currentLink} ---"
        start.call @, links[currentLink]
        addLinks.call @, links[currentLink]
        currentLink++
        @run check
    else
        @echo "All done."
        @exit()

casper.start()

casper.then ->
    @echo "Starting"

casper.run check
