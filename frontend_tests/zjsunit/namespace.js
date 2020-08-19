"use strict";

const _ = require("lodash");

const requires = [];
const new_globals = new Set();
let old_globals = {};

exports.set_global = function (name, val) {
    if (!(name in old_globals)) {
        if (!(name in global)) {
            new_globals.add(name);
        }
        old_globals[name] = global[name];
    }
    global[name] = val;
    return val;
};

function require_path(name, fn) {
    if (fn === undefined) {
        fn = "../../static/js/" + name;
    } else if (/^generated\/|^js\/|^shared\/|^third\//.test(fn)) {
        // FIXME: Stealing part of the NPM namespace is confusing.
        fn = "../../static/" + fn;
    }

    return fn;
}

exports.zrequire = function (name, fn) {
    fn = require_path(name, fn);
    requires.push(fn);
    return require(fn);
};

exports.reset_module = function (name, fn) {
    fn = require_path(name, fn);
    delete require.cache[require.resolve(fn)];
    return require(fn);
};

exports.clear_zulip_refs = function () {
    /*
        This is a big hammer to make sure
        we are not "borrowing" a transitively
        required module from a previous test.
        This kind of leak can make it seems
        like we've written the second test
        correctly, but it will fail if we
        run it standalone.
    */
    _.each(require.cache, (_, fn) => {
        if (fn.indexOf("static/") >= 0) {
            if (fn.indexOf("static/templates") < 0) {
                delete require.cache[fn];
            }
        }
    });
};

exports.restore = function () {
    requires.forEach((fn) => {
        delete require.cache[require.resolve(fn)];
    });
    Object.assign(global, old_globals);
    old_globals = {};
    for (const name of new_globals) {
        delete global[name];
    }
    new_globals.clear();
};

exports.stub_out_jquery = function () {
    set_global("$", () => ({
        on() {},
        trigger() {},
        hide() {},
        removeClass() {},
    }));
    $.fn = {};
    $.now = function () {};
};

exports.with_field = function (obj, field, val, f) {
    const old_val = obj[field];
    obj[field] = val;
    f();
    obj[field] = old_val;
};

exports.with_overrides = function (test_function) {
    // This function calls test_function() and passes in
    // a way to override the namespace temporarily.

    const restore_callbacks = [];
    const unused_funcs = new Map();

    const override = function (name, f) {
        if (typeof f !== "function") {
            throw new Error("You can only override with a function.");
        }

        unused_funcs.set(name, true);

        const parts = name.split(".");
        const module = parts[0];
        const func_name = parts[1];

        if (!Object.prototype.hasOwnProperty.call(global, module)) {
            throw new Error("you must first use set_global/zrequire for " + module);
        }

        const old_f = global[module][func_name];
        global[module][func_name] = function (...args) {
            unused_funcs.delete(name);
            return f.apply(this, args);
        };

        restore_callbacks.push(() => {
            global[module][func_name] = old_f;
        });
    };

    test_function(override);

    restore_callbacks.reverse();
    for (const restore_callback of restore_callbacks) {
        restore_callback();
    }

    for (const unused_name of unused_funcs.keys()) {
        throw new Error(unused_name + " never got invoked!");
    }
};
