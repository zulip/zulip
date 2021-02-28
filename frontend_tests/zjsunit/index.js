"use strict";

const fs = require("fs");
const Module = require("module");
const path = require("path");

require("css.escape");
const Handlebars = require("handlebars/runtime");
const _ = require("lodash");

const handlebars = require("./handlebars");
const stub_i18n = require("./i18n");
const namespace = require("./namespace");
const test = require("./test");
const {make_zblueslip} = require("./zblueslip");

global.$ = require("./zjquery");

require("@babel/register")({
    extensions: [".es6", ".es", ".jsx", ".js", ".mjs", ".ts"],
    only: [
        new RegExp("^" + _.escapeRegExp(path.resolve(__dirname, "../../static/js") + path.sep)),
        new RegExp(
            "^" + _.escapeRegExp(path.resolve(__dirname, "../../static/shared/js") + path.sep),
        ),
    ],
    plugins: ["babel-plugin-rewire-ts"],
});

// Create a helper function to avoid sneaky delays in tests.
function immediate(f) {
    return () => f();
}

// Find the files we need to run.
const files = process.argv.slice(2);
if (files.length === 0) {
    throw new Error("No tests found");
}

// Set up our namespace helpers.
const window = new Proxy(global, {
    set: (obj, prop, value) => {
        namespace.set_global(prop, value);
        return true;
    },
});

// Set up Handlebars
handlebars.hook_require();

const noop = function () {};

// Set up fake module.hot
Module.prototype.hot = {
    accept: noop,
};

function short_tb(tb) {
    let lines = tb.split("\n");

    try {
        let failing_line;

        for (const line of lines) {
            if (line.includes("static/js") || line.includes("frontend_tests/node_tests")) {
                failing_line = line;
                break;
            }
        }
        const re = /(\/.*?):(.*?):/;
        const arr = re.exec(failing_line);
        const fn = arr[1];
        const line_number = Number.parseInt(arr[2], 10);

        const file_lines = fs.readFileSync(fn, "utf8").split("\n");
        const begin = Math.max(line_number - 3, 0);
        const end = line_number + 3;

        const bad_lines = file_lines.slice(begin, end);

        lines = [...bad_lines, "", ...lines];
    } catch {
        // do nothing
    }

    let i;
    for (i = lines.length - 1; i >= 0; i -= 1) {
        if (lines[i].includes("frontend_tests/node_tests")) {
            break;
        }
    }

    if (i <= 0) {
        return tb;
    }

    return lines.splice(0, i + 1).join("\n") + "\n(...)\n";
}

function run_one_module(file) {
    global.$.clear_all_elements();
    console.info("running test " + path.basename(file, ".js"));
    test.set_current_file_name(file);
    require(file);
}

test.set_verbose(files.length === 1);

try {
    for (const file of files) {
        namespace.clear();
        namespace.set_global("window", window);
        namespace.set_global("to_$", () => window);
        namespace.set_global("location", {
            hash: "#",
        });
        namespace.set_global("setTimeout", noop);
        namespace.set_global("setInterval", noop);
        _.throttle = immediate;
        _.debounce = immediate;

        const blueslip = namespace.set_global("blueslip", make_zblueslip());
        namespace.set_global("i18n", stub_i18n);

        run_one_module(file);

        if (blueslip.reset) {
            blueslip.reset();
        }

        namespace.restore();
        Handlebars.HandlebarsEnvironment.call(Handlebars);
    }
} catch (error) {
    if (error.stack) {
        console.info(short_tb(error.stack));
    } else {
        console.info(error);
    }
    process.exit(1);
}
