"use strict";

const path = require("path");

require("css.escape");
require("handlebars/runtime");
const {JSDOM} = require("jsdom");
const _ = require("lodash");

const handlebars = require("./handlebars");
const stub_i18n = require("./i18n");
const namespace = require("./namespace");
const test = require("./test");
const blueslip = require("./zblueslip");
const zjquery = require("./zjquery");
const zpage_params = require("./zpage_params");

const dom = new JSDOM("", {url: "http://zulip.zulipdev.com/"});
global.DOMParser = dom.window.DOMParser;

require("@babel/register")({
    extensions: [".es6", ".es", ".jsx", ".js", ".mjs", ".ts"],
    only: [
        new RegExp("^" + _.escapeRegExp(path.resolve(__dirname, "../../static/js") + path.sep)),
        new RegExp(
            "^" + _.escapeRegExp(path.resolve(__dirname, "../../static/shared/js") + path.sep),
        ),
    ],
    plugins: [
        "babel-plugin-rewire-ts",
        ["@babel/plugin-transform-modules-commonjs", {lazy: () => true}],
    ],
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

function short_tb(tb) {
    const lines = tb.split("\n");

    const i = lines.findIndex((line) => line.includes("run_one_module"));

    if (i === -1) {
        return tb;
    }

    return lines.splice(0, i + 1).join("\n") + "\n(...)\n";
}

require("../../static/js/templates"); // register Zulip extensions

function run_one_module(file) {
    zjquery.clear_initialize_function();
    zjquery.clear_all_elements();
    console.info("running test " + path.basename(file, ".js"));
    test.set_current_file_name(file);
    require(file);
    namespace.complain_about_unused_mocks();
}

test.set_verbose(files.length === 1);

try {
    for (const file of files) {
        namespace.start();
        namespace.set_global("window", window);
        namespace.set_global("to_$", () => window);
        namespace.set_global("location", dom.window.location);
        window.location.href = "http://zulip.zulipdev.com/#";
        namespace.set_global("setTimeout", noop);
        namespace.set_global("setInterval", noop);
        _.throttle = immediate;
        _.debounce = immediate;
        zpage_params.reset();

        namespace.mock_esm("../../static/js/blueslip", blueslip);
        require("../../static/js/blueslip");
        namespace.mock_esm("../../static/js/i18n", stub_i18n);
        require("../../static/js/i18n");
        namespace.mock_esm("../../static/js/page_params", zpage_params);
        require("../../static/js/page_params");
        namespace.mock_esm("../../static/js/user_settings", zpage_params);
        require("../../static/js/user_settings");
        namespace.mock_esm("../../static/js/realm_user_settings_defaults", zpage_params);
        require("../../static/js/realm_user_settings_defaults");

        run_one_module(file);

        if (blueslip.reset) {
            blueslip.reset();
        }

        namespace.finish();
    }
} catch (error) {
    if (error.stack) {
        console.info(short_tb(error.stack));
    } else {
        console.info(error);
    }
    process.exit(1);
}
