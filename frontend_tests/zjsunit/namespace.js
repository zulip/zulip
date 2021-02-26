"use strict";

const path = require("path");

const new_globals = new Set();
let old_globals = {};

exports.set_global = function (name, val) {
    if (val === null) {
        throw new Error(`
            We try to avoid using null in our codebase.
        `);
    }

    // Add this for debugging and to allow with_overrides
    // to know that we're dealing with stubbed code.
    if (typeof val === "object") {
        val._patched_with_set_global = true;
    }

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
    return require(require_path(name, fn));
};

exports.reset_module = function (name, fn) {
    fn = require_path(name, fn);
    delete require.cache[require.resolve(fn)];
    return require(fn);
};

const staticPath = path.resolve(__dirname, "../../static") + path.sep;
const templatesPath = staticPath + "templates" + path.sep;

exports.restore = function () {
    for (const path of Object.keys(require.cache)) {
        if (path.startsWith(staticPath) && !path.startsWith(templatesPath)) {
            delete require.cache[path];
        }
    }
    Object.assign(global, old_globals);
    old_globals = {};
    for (const name of new_globals) {
        delete global[name];
    }
    new_globals.clear();
};

exports.with_field = function (obj, field, val, f) {
    if ("__esModule" in obj && "__Rewire__" in obj) {
        const old_val = field in obj ? obj[field] : obj.__GetDependency__(field);
        try {
            obj.__Rewire__(field, val);
            return f();
        } finally {
            obj.__Rewire__(field, old_val);
        }
    } else {
        const had_val = Object.prototype.hasOwnProperty.call(obj, field);
        const old_val = obj[field];
        try {
            obj[field] = val;
            return f();
        } finally {
            if (had_val) {
                obj[field] = old_val;
            } else {
                delete obj[field];
            }
        }
    }
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

        if (typeof obj !== "object" && typeof obj !== "function") {
            throw new TypeError(`We cannot override a function for ${typeof obj} objects`);
        }

        if (obj[func_name] === undefined) {
            if (obj !== global.$ && !obj._patched_with_set_global) {
                throw new Error(`
                    It looks like you are overriding ${func_name}
                    for a module that never defined it, which probably
                    indicates that you have a typo or are doing
                    something hacky in the test.
                `);
            }
        } else if (typeof obj[func_name] !== "function") {
            throw new TypeError(`
                You are overriding a non-function with a function.
                This is almost certainly an error.
            `);
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

        let old_f =
            "__esModule" in obj && "__Rewire__" in obj && !(func_name in obj)
                ? obj.__GetDependency__(func_name)
                : obj[func_name];
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

        if ("__esModule" in obj && "__Rewire__" in obj) {
            obj.__Rewire__(func_name, new_f);
            restore_callbacks.push(() => {
                obj.__Rewire__(func_name, old_f);
            });
        } else {
            obj[func_name] = new_f;
            restore_callbacks.push(() => {
                old_f._patched_with_override = true;
                obj[func_name] = old_f;
                delete old_f._patched_with_override;
            });
        }
    };

    try {
        test_function(override);
    } finally {
        restore_callbacks.reverse();
        for (const restore_callback of restore_callbacks) {
            restore_callback();
        }
    }

    for (const module_unused_funcs of unused_funcs.values()) {
        for (const unused_name of module_unused_funcs.keys()) {
            throw new Error(unused_name + " never got invoked!");
        }
    }
};
