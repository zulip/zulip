#!/usr/bin/env node

/*
The MIT License (MIT)

Copyright (c) 2015 Khan Academy

This software also uses portions of the underscore.js project, which is
MIT licensed with the following copyright:

Copyright (c) 2009-2015 Jeremy Ashkenas, DocumentCloud and Investigative
Reporters & Editors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/

// Simple CLI for KaTeX.
// Reads TeX from stdin, outputs HTML to stdout.

let katex;
try {
    // Attempt to import KaTeX from the production bundle
    katex = require("/home/zulip/prod-static/min/katex.js");
} catch (ex) {
    // Import KaTeX from node_modules (development environment) otherwise
    katex = require("../../node_modules/katex/dist/katex.js");
}

let input = "";

// Skip the first two args, which are just "node" and "cli.js"
const args = process.argv.slice(2);

if (args.indexOf("--help") !== -1) {
    console.log(process.argv[0] + " " + process.argv[1] +
                " [ --help ]" +
                " [ --display-mode ]");

    console.log("\n" +
                "Options:");
    console.log("  --help            Display this help message");
    console.log("  --display-mode    Render in display mode (not inline mode)");
    process.exit();
}

process.stdin.on("data", function(chunk) {
    input += chunk.toString();
});

process.stdin.on("end", function() {
    var options = { displayMode: args.indexOf("--display-mode") !== -1 };
    var output = katex.renderToString(input, options);
    console.log(output);
});
