"use strict";

const path = require("path");

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
    const staticPath = path.resolve(__dirname, "../../static") + path.sep;
    _.each(require.cache, (_, fn) => {
        if (fn.startsWith(staticPath) && !fn.startsWith(staticPath + "templates" + path.sep)) {
            delete require.cache[fn];
        }
    });
};

exports.restore = function () {
    for (const fn of requires) {
        delete require.cache[require.resolve(fn)];
    }
    Object.assign(global, old_globals);
    old_globals = {};
    for (const name of new_globals) {
        delete global[name];
    }
    new_globals.clear();
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
    const funcs = new Map();

    const override = function (obj, func_name, f) {
        // Given an object `obj` (which is usually a module object),
        // we re-map `obj[func_name]` to the `f` passed in by the caller.
        // Then the outer function here (`with_overrides`) automatically
        // restores the original value of `obj[func_name]` as its last
        // step.  Generally our code calls `run_test`, which wraps
        // `with_overrides`.
        if (typeof f !== "function") {
            throw new TypeError(
                "You can only override with a function. Use with_field for non-functions.",
            );
        }

        if (!funcs.has(obj)) {
            funcs.set(obj, new Map());
        }

        if (funcs.get(obj).has(func_name)) {
            // Prevent overriding the same function twice, so that
            // it's super easy to reason about our logic to restore
            // the original function.  Usually if somebody sees this
            // error, it's a symptom of not breaking up tests enough.
            throw new Error(
                "You can only override a function one time. Use with_field for more granular control.",
            );
        }

        funcs.get(obj).set(func_name, true);

        if (!unused_funcs.has(obj)) {
            unused_funcs.set(obj, new Map());
        }

        unused_funcs.get(obj).set(func_name, true);

        let old_f = obj[func_name];
        if (old_f === undefined) {
            // Create a dummy function so that we can
            // attach _patched_with_override to it.
            old_f = () => {
                throw new Error(`There is no ${func_name}() field for this object.`);
            };
        }

        const new_f = function (...args) {
            unused_funcs.get(obj).delete(func_name);
            return f.apply(this, args);
        };

        // Let zjquery know this function was patched with override,
        // so it doesn't complain about us modifying it.  (Other
        // code can also use this, as needed.)
        new_f._patched_with_override = true;

        obj[func_name] = new_f;

        restore_callbacks.push(() => {
            old_f._patched_with_override = true;
            obj[func_name] = old_f;
            delete old_f._patched_with_override;
        });
    };

    test_function(override);

    restore_callbacks.reverse();
    for (const restore_callback of restore_callbacks) {
        restore_callback();
    }

    for (const module_unused_funcs of unused_funcs.values()) {
        for (const unused_name of module_unused_funcs.keys()) {
            throw new Error(unused_name + " never got invoked!");
        }
    }
};
