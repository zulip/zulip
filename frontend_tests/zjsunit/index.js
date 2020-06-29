const path = require('path');
const fs = require('fs');
const escapeRegExp = require("lodash/escapeRegExp");

require("@babel/register")({
    extensions: [".es6", ".es", ".jsx", ".js", ".mjs", ".ts"],
    only: [
        new RegExp("^" + escapeRegExp(path.resolve(__dirname, "../../static/js")) + path.sep),
        new RegExp("^" + escapeRegExp(path.resolve(__dirname, "../../static/shared/js")) + path.sep),
    ],
    plugins: ["rewire-ts"],
});

global.assert = require('assert').strict;
global._ = require('underscore/underscore.js');
const _ = global._;

// Create a helper function to avoid sneaky delays in tests.
function immediate(f) {
    return () => {
        return f();
    };
}

// Find the files we need to run.
const finder = require('./finder.js');
const files = finder.find_files_to_run(); // may write to console
if (files.length === 0) {
    throw "No tests found";
}

// Set up our namespace helpers.
const namespace = require('./namespace.js');
global.set_global = namespace.set_global;
global.patch_builtin = namespace.set_global;
global.zrequire = namespace.zrequire;
global.stub_out_jquery = namespace.stub_out_jquery;
global.with_overrides = namespace.with_overrides;

global.window = new Proxy(global, {
    set: (obj, prop, value) => namespace.set_global(prop, value),
});
global.to_$ = () => window;

// Set up stub helpers.
const stub = require('./stub.js');
global.make_stub = stub.make_stub;
global.with_stub = stub.with_stub;

// Set up fake jQuery
global.make_zjquery = require('./zjquery.js').make_zjquery;

// Set up fake blueslip
const make_blueslip = require('./zblueslip.js').make_zblueslip;

// Set up fake translation
const stub_i18n = require('./i18n.js');

// Set up Handlebars
const handlebars = require('./handlebars.js');
global.make_handlebars = handlebars.make_handlebars;
global.stub_templates = handlebars.stub_templates;

const noop = function () {};

// Set up fake module.hot
const Module = require('module');
Module.prototype.hot = {
    accept: noop,
};

// Set up fixtures.
global.read_fixture_data = (fn) => {
    const full_fn = path.join(__dirname, '../../zerver/tests/fixtures/', fn);
    const data = JSON.parse(fs.readFileSync(full_fn, 'utf8', 'r'));
    return data;
};

function short_tb(tb) {
    const lines = tb.split('\n');

    const i = lines.findIndex(line => line.includes('run_test') || line.includes('run_one_module'));

    if (i === -1) {
        return tb;
    }

    return lines.splice(0, i + 1).join('\n') + '\n(...)\n';
}

// Set up markdown comparison helper
global.markdown_assert = require('./markdown_assert.js');

function run_one_module(file) {
    console.info('running tests for ' + file.name);
    require(file.full_name);
}

global.run_test = (label, f) => {
    if (files.length === 1) {
        console.info('        test: ' + label);
    }
    f();
    // defensively reset blueslip after each test.
    blueslip.reset();
};

try {
    files.forEach(function (file) {
        set_global('location', {
            hash: '#',
        });
        global.patch_builtin('setTimeout', noop);
        global.patch_builtin('setInterval', noop);
        _.throttle = immediate;
        _.debounce = immediate;

        set_global('blueslip', make_blueslip());
        set_global('i18n', stub_i18n);
        namespace.clear_zulip_refs();

        run_one_module(file);

        if (blueslip.reset) {
            blueslip.reset();
        }

        namespace.restore();
    });
} catch (e) {
    if (e.stack) {
        console.info(short_tb(e.stack));
    } else {
        console.info(e);
    }
    process.exit(1);
}
