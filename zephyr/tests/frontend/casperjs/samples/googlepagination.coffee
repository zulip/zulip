###
Capture multiple pages of google search results

Usage: $ casperjs googlepagination.coffee my search terms

(all arguments will be used as the query)
###

casper = require("casper").create()
currentPage = 1

if casper.cli.args.length is 0
    casper
        .echo("Usage: $ casperjs googlepagination.coffee my search terms")
        .exit(1)

processPage = ->
    @echo "capturing page #{currentPage}"
    @capture "google-results-p#{currentPage}.png"

    # don't go too far down the rabbit hole
    return if currentPage >= 5

    if @exists "#pnnext"
        currentPage++
        @echo "requesting next page: #{currentPage}"
        url = @getCurrentUrl()
        @thenClick("#pnnext").then ->
            @waitFor (->
                url isnt @getCurrentUrl()
            ), processPage
    else
        @echo "that's all, folks."

casper.start "http://google.fr/", ->
    @fill 'form[action="/search"]',  q: casper.cli.args.join(" "), true

casper.then processPage

casper.run()
