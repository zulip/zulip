###
This script will capture a screenshot of a twitter account page
Usage: $ casperjs screenshot.coffee <twitter-account> <filename.[jpg|png|pdf]>
###

casper = require("casper").create
    viewportSize:
        width: 1024
        height: 768

twitterAccount = casper.cli.get 0
filename       = casper.cli.get 1

if not twitterAccount or not filename or not /\.(png|jpg|pdf)$/i.test filename
    casper
        .echo("Usage: $ casperjs screenshot.coffee <twitter-account> <filename.[jpg|png|pdf]>")
        .exit(1)

casper.start "https://twitter.com/#{twitterAccount}", ->
    @waitForSelector ".stream-container", (->
        @captureSelector filename, "html"
        @echo "Saved screenshot of #{@getCurrentUrl()} to #{filename}"
    ), (->
        @die("Timeout reached. Fail whale?")
        @exit()
    ), 12000

casper.run()
