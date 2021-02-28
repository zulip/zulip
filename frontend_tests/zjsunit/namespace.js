"use strict";

const path = require("path");

const new_globals = new Set();
let old_globals = {};

let objs_installed;
let mock_paths = {};
let mocked_paths;
let mock_names;

exports.clear = () => {
    objs_installed = false;
    mock_paths = {};
    mocked_paths = new Set();
    mock_names = new Set();
};

function get_short_name(fn) {
    return path.parse(path.basename(fn)).name;
}

exports.rewiremock = (fn) => {
    if (!fn.startsWith("../../static/js/")) {
        throw new Error(`We only mock static/js files`);
    }
    const short_fn = fn.slice("../../static/js/".length);
    const base_path = path.resolve("./static/js");
    const long_fn = path.join(base_path, short_fn);

    return {
        with: (obj) => {
            if (objs_installed) {
                throw new Error(`
                    It is too late to install this mock.  Consider instead:

                        foo.__Rewire__(${short_fn}, ...)

                    Or call this earlier.
                `);
            }
            obj.__esModule = true;
            mock_paths[long_fn] = obj;
            mock_names.add(short_fn);
            return obj;
        },
    };
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

function proxy_dummy(name, request) {
    function error_message(prop) {
        return `
            The code you are calling is trying to use ${prop}
            while compiling/using ${name}.

            Maybe it's about ${request}?

            You need to modify your call to use() to address
            this transitive dependency.
        `;
    }

    return new Proxy(
        {__dummy: true, __esModule: true},
        {
            get(obj, prop) {
                if (!obj[prop]) {
                    throw new Error(error_message(prop));
                }
                return obj[prop];
            },
            set(obj, prop) {
                throw new Error(error_message(prop));
            },
        },
    );
}

function install_zulip_modules(...relative_paths) {
    const zulip_static = path.resolve("./static");
    const objs = {};
    const full_paths = {};
    const forward_refs = [];
    const parents = {};

    // All paths are relative to static/js
    for (const name of relative_paths) {
        const full_path = path.resolve(path.join("static/js", name));
        const short_name = get_short_name(full_path);

        if (!full_path.includes(zulip_static)) {
            throw new Error(`Path is outside of ${zulip_static}`);
        }

        if (full_paths[short_name]) {
            throw new Error(`
                You either repeated ${short_name} or you are
                using two files with the same name, which is
                extremely confusing.
            `);
        }
        if (mock_names.has(short_name)) {
            throw new Error(`
                You set up a mock for ${short_name}.
                So don't try to compile it, please.
            `);
        }
        full_paths[short_name] = full_path;
    }

    const actual_load = require("module")._load;

    require("module")._load = (request, parent, isMain) => {
        if (!parent.filename.includes(zulip_static)) {
            return actual_load(request, parent, isMain);
        }

        if (request.endsWith(".hbs")) {
            // Handlebar templates don't have any state,
            // and they are usually small,
            // so we just import them normally.
            return actual_load(request, parent, isMain);
        }

        if (request.endsWith(".json")) {
            return actual_load(request, parent, isMain);
        }

        const short_name = get_short_name(request);

        if (!request.startsWith(".")) {
            // Any non-relative path is probably something
            // like core-js.
            return actual_load(request, parent, isMain);
        }

        const long_fn = path.resolve(path.join(path.dirname(parent.filename), request));

        if (mock_paths[long_fn]) {
            mocked_paths.add(long_fn);
            return mock_paths[long_fn];
        }

        // We are trying to import a Zulip module that was already
        // compiled.  This is the happiest path.
        if (objs[short_name]) {
            return objs[short_name];
        }

        // We are trying to forward-load a module.
        const parent_short_name = get_short_name(parent.filename);
        if (full_paths[parent_short_name] && full_paths[short_name]) {
            parents[short_name] = parents[short_name] || [];
            parents[short_name].push(parent_short_name);

            // It is sometimes impossible to load in complete topological order,
            // but we complain about egregious violations.
            if (parents[short_name].length >= 4) {
                throw new Error(`
                    Please put ${short_name} earlier in the use statment.
                    A lot of modules depend on it.

                    We try to load in roughly topological order.
                `);
            }
            const forward_ref = {
                parent: parent_short_name,
                child: short_name,
            };
            // We push the forward_ref into a list so that we can resolve
            // it later. And then we also return a stub object to ensure
            // correct resolution. Read further down for more discussion.
            forward_refs.push(forward_ref);
            return {child: short_name};
        }

        return proxy_dummy(path.basename(parent.filename), request);
    };

    for (const [short_name, full_path] of Object.entries(full_paths)) {
        const result = require(full_path);
        objs[short_name] = result;
    }

    for (const fn of Object.keys(mock_paths)) {
        if (!mocked_paths.has(fn)) {
            throw new Error(`
                You asked to rewire ${fn} but we never
                saw it during compilation.
            `);
        }
    }

    for (const forward_ref of forward_refs) {
        const parent = forward_ref.parent;
        const child = forward_ref.child;
        if (typeof objs[parent] !== "object") {
            throw new TypeError(`
                We assumed ${parent} would be a normal JS object.
            `);
        }

        if (typeof objs[parent].__get__ !== "function") {
            throw new TypeError(`
                We assumed ${parent} would have a __get__
                function set up by babel to find dependent objects.
            `);
        }

        /*
            The following code deals with circular references like below:

                // bar.js
                import * as foo from "./foo";

                // foo.js
                import * as bar from "./bar";

            We have to load one of the modules first, and the first
            module we load won't have a compiled version of the second
            available.

            As long as we follow the `import * as foo from "./foo"`
            convention, this is no problem, and the code below
            just rewires the child with the __Rewire__ helper.

            It's also trivial to detect when code violates our
            assumption, even if somebody does something sinister
            like this:

                import * as drink from "./eat";
                import * as eat from "./drink";

            But what we don't handle is legitimate idioms like
            the following:

                import {FoldDict} from "./fold_dict";

            The problem is that I haven't figured out how to
            introspect how the parent is destructuring the
            object in the import statement during the above
            call to module._load.  I think it's just not available.

            I also couldn't find an obvious way to introspect the
            parent object to find the stub that we return in
            module._load.

            It wouldn't be crazy to just read the top of the parent JS
            file to learn how we import the target, but there has to
            be a better way.  We could also do something like having
            a canned list of known imports that we need to rewrite,
            but that feels fragile.

            For now I just punt if the parent did not import the
            child into the expected name of the child.

            Practically speaking, we can often just work around this
            in the actual node test, as the long error message below
            describes.
        */

        const stub = objs[parent].__get__(child);

        if (!stub || stub.child !== child) {
            throw new Error(`
                You tried to load "${parent}" before "${child}",
                which forces us to resolve the forward reference.

                We tried to guess the name that "${parent}"
                imports "${child}" as being just "${child}", but
                apparently we guessed wrong.

                There are a couple possible remedies here:

                    1. Put "${child}" earlier in the use statement.
                    2. Follow the normal naming convention to import "${child}".
                    3. Fix any circular dependencies.  (This can be hard but worthwhile.)
                    4. Use mock_module if the behavior of "${child}" is immaterial to your test.
            `);
        }

        objs[parent].__Rewire__(child, objs[child]);
    }

    const result = {};
    for (const [name, obj] of Object.entries(objs)) {
        result[name] = obj;
    }

    return result;
}

exports.use = (...relative_paths) => {
    const actual_load = require("module")._load;
    try {
        return install_zulip_modules(...relative_paths);
    } finally {
        require("module")._load = actual_load;
        objs_installed = true;
    }
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

        if (obj[func_name] !== undefined && typeof obj[func_name] !== "function") {
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
