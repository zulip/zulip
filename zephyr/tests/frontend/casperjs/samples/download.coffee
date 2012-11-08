###
Download the google logo image onto the local filesystem
###

casper = require("casper").create()

casper.start "http://www.google.fr/", ->
    @echo @download "http://www.google.fr/images/srpr/logo3w.png", "logo.png"

casper.run()
