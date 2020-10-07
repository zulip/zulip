"use strict";

const fs = require("fs");
const Module = require("module");
const path = require("path");

const Handlebars = require("handlebars/runtime");
const _ = require("lodash");

const handlebars = require("./handlebars");
const stub_i18n = require("./i18n");
const namespace = require("./namespace");
const stub = require("./stub");
const {make_zblueslip} = require("./zblueslip");
const zjquery = require("./zjquery");

require("@babel/register")({
    extensions: [".es6", ".es", ".jsx", ".js", ".mjs", ".ts"],
    only: [
        new RegExp("^" + _.escapeRegExp(path.resolve(__dirname, "../../static/js")) + path.sep),
        new RegExp(
            "^" + _.escapeRegExp(path.resolve(__dirname, "../../static/shared/js")) + path.sep,
        ),
    ],
    plugins: ["rewire-ts"],
});

global.assert = require("assert").strict;

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
global.with_field = namespace.with_field;
global.set_global = namespace.set_global;
global.patch_builtin = namespace.set_global;
global.zrequire = namespace.zrequire;
global.reset_module = namespace.reset_module;
global.stub_out_jquery = namespace.stub_out_jquery;
global.with_overrides = namespace.with_overrides;

global.window = new Proxy(global, {
    set: (obj, prop, value) => {
        namespace.set_global(prop, value);
        return true;
    },
});
global.to_$ = () => window;

// Set up stub helpers.
global.make_stub = stub.make_stub;
global.with_stub = stub.with_stub;

// Set up fake jQuery
global.make_zjquery = zjquery.make_zjquery;

// Set up Handlebars
global.stub_templates = handlebars.stub_templates;

const noop = function () {};

// Set up fake module.hot
Module.prototype.hot = {
    accept: noop,
};

// Set up fixtures.
global.read_fixture_data = (fn) => {
    const full_fn = path.join(__dirname, "../../zerver/tests/fixtures/", fn);
    const data = JSON.parse(fs.readFileSync(full_fn, "utf8", "r"));
    return data;
};

function short_tb(tb) {
    const lines = tb.split("\n");

    const i = lines.findIndex(
        (line) => line.includes("run_test") || line.includes("run_one_module"),
    );

    if (i === -1) {
        return tb;
    }

    return lines.splice(0, i + 1).join("\n") + "\n(...)\n";
}

// Set up Markdown comparison helper
global.markdown_assert = require("./markdown_assert");

let current_file_name;

function run_one_module(file) {
    console.info("running test " + path.basename(file, ".js"));
    current_file_name = file;
    require(file);
}

global.run_test = (label, f) => {
    if (files.length === 1) {
        console.info("        test: " + label);
    }
    try {
        global.with_overrides(f);
    } catch (error) {
        console.info("-".repeat(50));
        console.info(`test failed: ${current_file_name} > ${label}`);
        console.info();
        throw error;
    }
    // defensively reset blueslip after each test.
    blueslip.reset();
};

try {
    files.forEach((file) => {
        set_global("location", {
            hash: "#",
        });
        global.patch_builtin("setTimeout", noop);
        global.patch_builtin("setInterval", noop);
        _.throttle = immediate;
        _.debounce = immediate;

        set_global("blueslip", make_zblueslip());
        set_global("i18n", stub_i18n);
        namespace.clear_zulip_refs();

        run_one_module(file);

        if (blueslip.reset) {
            blueslip.reset();
        }

        namespace.restore();
        Handlebars.HandlebarsEnvironment();
    });
} catch (error) {
    if (error.stack) {
        console.info(short_tb(error.stack));
    } else {
        console.info(error);
    }
    process.exit(1);
}
