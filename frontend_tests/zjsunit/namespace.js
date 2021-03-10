"use strict";

const Module = require("module");
const path = require("path");

const new_globals = new Set();
let old_globals = {};

let actual_load;
let objs_installed;
const module_mocks = new Map();
let mocked_paths;

function load(request, parent, isMain) {
    const long_fn = path.resolve(path.join(path.dirname(parent.filename), request));
    if (module_mocks.has(long_fn)) {
        mocked_paths.add(long_fn);
        return module_mocks.get(long_fn);
    }

    return actual_load(request, parent, isMain);
}

exports.start = () => {
    if (actual_load !== undefined) {
        throw new Error("namespace.start was called twice in a row.");
    }
    actual_load = Module._load;
    Module._load = load;

    objs_installed = false;
    module_mocks.clear();
    mocked_paths = new Set();
};

exports.mock_module = (short_fn, obj) => {
    if (obj === undefined) {
        obj = {};
    }

    if (typeof obj !== "object") {
        throw new TypeError("We expect you to stub with an object.");
    }

    if (short_fn.startsWith("/") || short_fn.includes(".")) {
        throw new Error(`
            There is no need for a path like ${short_fn}.
            We just assume the file is under static/js.
        `);
    }
    if (objs_installed) {
        throw new Error(`
            It is too late to install this mock.  Consider instead:

                foo.__Rewire__("${short_fn}", ...)

            Or call this earlier.
        `);
    }

    const base_path = path.resolve("./static/js");
    const long_fn = path.join(base_path, short_fn);

    if (module_mocks.has(long_fn)) {
        throw new Error(`You already set up a mock for ${long_fn}`);
    }

    obj.__esModule = true;
    module_mocks.set(long_fn, obj);
    return obj;
};

exports.set_global = function (name, val) {
    if (val === null) {
        throw new Error(`
            We try to avoid using null in our codebase.
        `);
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

exports.zrequire = function (fn) {
    objs_installed = true;
    const full_path = path.resolve(path.join("static/js", fn));
    return require(full_path);
};

const staticPath = path.resolve(__dirname, "../../static") + path.sep;
const templatesPath = staticPath + "templates" + path.sep;

exports.finish = function () {
    /*
        Handle cleanup tasks after we've run one module.

        Note that we currently do lazy compilation of modules,
        so we need to wait till the module tests finish
        running to do things like detecting pointless mocks
        and resetting our _load hook.
    */
    if (actual_load === undefined) {
        throw new Error("namespace.finish was called without namespace.start.");
    }
    Module._load = actual_load;
    actual_load = undefined;

    for (const fn of module_mocks.keys()) {
        if (!mocked_paths.has(fn)) {
            throw new Error(`
                You asked to mock ${fn} but we never
                saw it during compilation.
            `);
        }
    }

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

        if (obj[func_name] !== undefined && typeof obj[func_name] !== "function") {
            throw new TypeError(`
                You are overriding a non-function with a function.
                This is almost certainly an error.
            `);
        }

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
