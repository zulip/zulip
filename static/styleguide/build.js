(() => {
    var fs = require("fs"),
        compressor = require("node-minify");

    var timer = function () {
        var meta = {
            start: new Date(),
            last: new Date()
        };

        return {
            since: function () {
                var diff = new Date() - meta.last;
                meta.last = new Date();
                return diff;
            },
            total: function () {
                return new Date() - meta.start;
            },
            reset: function () {
                meta = {
                    start: new Date(),
                    last: new Date()
                };
            }
        };
    };
    var compress = function (dir, files, output, callback, compress) {
        var data = [],
            counter = 0;

        var file = {
            write: function (data) {
                fs.writeFile(output, data, function (err, response) {
                    console.log("Files written in " + t.since() + "ms.");
                    if (compress !== false) {
                        file.compress();
                    } else {
                        callback();
                    }
                });
            },
            compress: function (data) {
                new compressor.minify({
                    type: 'uglifyjs',
                    fileIn: output,
                    fileOut: 'dist/all.min.js',
                    callback: function (err, min) {
                        console.log("Files minified in " + t.since() + "ms.");
                        callback(data);
                    }
                });
            }
        };

        files.forEach(function (o, i) {
            fs.readFile(dir + o, "utf8", function (err, response) {
                data[i] = response;
                counter++;

                if (counter === files.length) {
                    file.write(data.join("\n"));
                    console.log("Files read and joined in " + t.since() + "ms.");
                }

                if (err) {
                    console.warn(err);
                }
            });
        });
    };

    var t = timer(),
        cmd;

    if (process.argv) {
        cmd = {
            js: function (callback) {
                var dir = "public/js/";

                var files = [
                    "vendor/highlight.pack.js",
                    "tools/events.js",
                    "tools/parser.js",
                    "tools/templater.js",
                    "tools/tools.js",
                    "tools/storage.js",
                    "events.js",
                    "load.js",
                    "main.js",
                    "ui.js",
                    "get-config.js"
                ];

                compress(dir, files, "dist/all.js", function (data) {
                    console.log("JavaScript completed in " + t.total() + "ms.");
                    if (callback) callback();
                });
            },
            css: function (callback) {
                var dir = "public/css/";

                var files = [
                    "atom-one-light.css",
                    "components.css",
                    "main.css"
                ];

                t.reset();

                compress(dir, files, "public/css/style.css", function (data) {
                    console.log("CSS completed in " + t.total() + "ms.");
                    if (callback) callback();
                }, false);
            }
        };
    }

    var key = process.argv[2];

    if (!key || key === "all") {
        cmd.js(function () {
            cmd.css();
        });
    } else if (cmd[key]) {
        cmd[key](function () {

        });
    }
}());
