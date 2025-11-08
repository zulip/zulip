"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");

require("css.escape");
require("handlebars/runtime.js");
const {JSDOM} = require("jsdom");
const _ = require("lodash");

const handlebars = require("./handlebars.cjs");
const stub_i18n = require("./i18n.cjs");
const namespace = require("./namespace.cjs");
const test = require("./test.cjs");
const blueslip = require("./zblueslip.cjs");
const zjquery = require("./zjquery.cjs");
const zpage_billing_params = require("./zpage_billing_params.cjs");
const zpage_params = require("./zpage_params.cjs");

process.env.NODE_ENV = "test";

const dom = new JSDOM("", {url: "http://zulip.zulipdev.com/"});
global.DOMParser = dom.window.DOMParser;
global.HTMLAnchorElement = dom.window.HTMLAnchorElement;
global.HTMLElement = dom.window.HTMLElement;
global.HTMLImageElement = dom.window.HTMLImageElement;
global.Window = dom.window.Window;
Object.defineProperty(global, "navigator", {
    value: {
        userAgent: "node.js",
    },
    writable: true,
});

require("@babel/register")({
    extensions: [".cjs", ".cts", ".js", ".mjs", ".mts", ".ts"],
    only: [
        new RegExp("^" + _.escapeRegExp(path.resolve(__dirname, "../../shared/src") + path.sep)),
        new RegExp("^" + _.escapeRegExp(path.resolve(__dirname, "../../src") + path.sep)),
    ],
    plugins: [
        ...(process.env.USING_INSTRUMENTED_CODE ? [["istanbul", {exclude: []}]] : []),
        ["@babel/plugin-transform-modules-commonjs", {lazy: () => true}],
    ],
    root: path.resolve(__dirname, "../.."),
});

// Create a helper function to avoid sneaky delays in tests.
function immediate(f) {
    return () => f();
}

// Find the files we need to run.
const files = process.argv.slice(2);
assert.notEqual(files.length, 0, "No tests found");

// Set up our namespace helpers.
const window = new Proxy(global, {
    set(_obj, prop, value) {
        namespace.set_global(prop, value);
        return true;
    },
});

const ls_container = new Map();
const localStorage = {
    getItem(key) {
        return ls_container.get(key);
    },
    setItem(key, val) {
        ls_container.set(key, val);
    },
    /* istanbul ignore next */
    removeItem(key) {
        ls_container.delete(key);
    },
    clear() {
        ls_container.clear();
    },
};

// Set up Handlebars
handlebars.hook_require();

const noop = function () {};

require("../../src/templates.ts"); // register Zulip extensions

async function run_one_module(file) {
    zjquery.clear_all_elements();
    console.info("running test " + path.basename(file, ".test.cjs"));
    test.set_current_file_name(file);
    test.suite.length = 0;
    require(file);
    for (const f of test.suite) {
        await f();
    }
    namespace.complain_about_unused_mocks();
}

test.set_verbose(files.length === 1);

// In case someone mistakenly vanishes the async task with something like `await
// new Promise(() => {})`, assume failure until we establish otherwise.
process.exitCode = 1;

(async () => {
    let exit_code = 0;

    for (const file of files) {
        namespace.start();
        namespace.set_global("window", window);
        namespace.set_global("location", dom.window.location);
        window.location.href = "http://zulip.zulipdev.com/#";
        namespace.set_global("setTimeout", noop);
        namespace.set_global("setInterval", noop);
        namespace.set_global("localStorage", localStorage);
        ls_container.clear();
        _.throttle = immediate;
        _.debounce = immediate;
        zpage_billing_params.reset();
        zpage_params.reset();

        namespace.mock_esm("../../src/blueslip", blueslip);
        require("../../src/blueslip.ts");
        namespace.mock_esm("../../src/i18n", stub_i18n);
        require("../../src/i18n.ts");
        namespace.mock_esm("../../src/base_page_params", zpage_params);
        require("../../src/base_page_params.ts");
        namespace.mock_esm("../../src/billing/page_params", zpage_billing_params);
        require("../../src/billing/page_params.ts");
        namespace.mock_esm("../../src/page_params", zpage_params);
        require("../../src/page_params.ts");

        // Make sure we re-register our Handlebars helpers.
        require("../../src/templates.ts");

        try {
            await run_one_module(file);
            blueslip.reset();
        } catch (error) /* istanbul ignore next */ {
            console.error(error);
            exit_code = 1;
            blueslip.reset(true);
        }

        namespace.finish();
    }

    process.exitCode = exit_code;
})().catch((error) => /* istanbul ignore next */ {
    console.error(error);
});
