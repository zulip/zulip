###
A basic custom logging implementation. The idea is to (extremely) verbosely
log every received resource.
###

casper = require("casper").create
    ###
    Every time a resource is received, a new log entry is added to the stack
    at the 'verbose' level.

    @param  Object  resource  A phantomjs resource object
    ###
    onResourceReceived: (self, resource) ->
        infos = []
        props = [
            "url"
            "status"
            "statusText"
            "redirectURL"
            "bodySize"
        ]
        infos.push resource[prop] for prop in props
        infos.push "[#{header.name}: #{header.value}]" for header in resource.headers
        @log infos.join(", "), "verbose"
    verbose: true       # we want to see the log printed out to the console
    logLevel: "verbose" # of course we want to see logs to our new level :)

# add a new 'verbose' logging level at the lowest priority
casper.logLevels = ["verbose"].concat casper.logLevels

# test our new logger with google
casper.start("http://www.google.com/").run ->
    @exit()
