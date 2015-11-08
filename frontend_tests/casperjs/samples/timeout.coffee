###
Just a silly game.

$ casperjs samples/timeout.js 500
Will google.com load in less than 500ms?
NOPE.

$ casperjs samples/timeout.js 1000
Will google.com load in less than 1000ms?
NOPE.

$ casperjs samples/timeout.js 1500
Will google.com load in less than 1500ms?
NOPE.

$ casperjs samples/timeout.js 2000
Will google.com load in less than 2000ms?
YES!
###

casper = require("casper").create
    onTimeout: ->
        @echo "NOPE.", "RED_BAR"
        @exit()

timeout = ~~casper.cli.get 0
if timeout < 1
    casper
        .echo("You must pass a valid timeout value")
        .exit(1)

casper.echo "Will google.com load in less than #{timeout}ms?"
casper.options.timeout = timeout

casper.start "http://www.google.com/", ->
    @echo "YES!", "GREEN_BAR"
    @exit()

casper.run()