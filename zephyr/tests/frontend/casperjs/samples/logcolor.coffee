casper = require("casper").create
    verbose: true
    logLevel: "debug"

casper.log "this is a debug message", "debug"
casper.log "and an informative one", "info"
casper.log "and a warning", "warning"
casper.log "and an error", "error"

casper.exit()
