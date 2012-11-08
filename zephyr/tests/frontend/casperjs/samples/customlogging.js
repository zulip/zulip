/*
 * A basic custom logging implementation. The idea is to (extremely) verbosely
 * log every received resource.
 */

var casper = require("casper").create({
    /*
    Every time a resource is received, a new log entry is added to the stack at
    the 'verbose' level.
    */
    onResourceReceived: function(self, resource) {
        var header, infos, prop, props, _i, _j, _len, _len1, _ref;
        infos = [];
        props = [
            "url",
            "status",
            "statusText",
            "redirectURL",
            "bodySize"
        ];
        for (_i = 0, _len = props.length; _i < _len; _i++) {
            prop = props[_i];
            infos.push(resource[prop]);
        }
        _ref = resource.headers;
        for (_j = 0, _len1 = _ref.length; _j < _len1; _j++) {
            header = _ref[_j];
            infos.push("[" + header.name + ": " + header.value + "]");
        }
        this.log(infos.join(", "), "verbose");
    },
    verbose: true,
    logLevel: "verbose"
});

// add a new 'verbose' logging level at the lowest priority
casper.logLevels = ["verbose"].concat(casper.logLevels);

// test our new logger with google
casper.start("http://www.google.com/").run(function() {
    this.exit();
});
