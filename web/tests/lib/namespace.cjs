"use strict";

const assert = require("node:assert/strict");
const Module = require("node:module");
const path = require("node:path");

const {default: callsites} = require("callsites");

const $ = require("./zjquery.cjs");

const new_globals = new Set();
let old_globals = {};

let actual_load;
const module_mocks = new Map();
const template_mocks = new Map();
const used_module_mocks = new Set();
const used_templates = new Set();

const jquery_path = require.resolve("jquery");
const real_jquery_path = require.resolve("./real_jquery.cjs");

let in_mid_render = false;
let jquery_function;

const template_path = path.resolve(__dirname, "../../templates");

function load(request, parent, isMain) {
    const filename = Module._resolveFilename(request, parent, isMain);
    if (module_mocks.has(filename)) {
        used_module_mocks.add(filename);
        return module_mocks.get(filename);
    } else if (filename.endsWith(".hbs") && filename.startsWith(template_path + path.sep)) {
        const actual_render = actual_load(request, parent, isMain);
        return template_stub({filename, actual_render});
    } else if (filename === jquery_path && parent.filename !== real_jquery_path) {
        return jquery_function || $;
    }

    const module = actual_load(request, parent, isMain);
    if ((typeof module === "object" || typeof module === "function") && "__esModule" in module) {
        /* istanbul ignore next */
        function error_immutable() {
            throw new Error(`${filename} is an immutable ES module`);
        }
        return new Proxy(module, {
            defineProperty: error_immutable,
            deleteProperty: error_immutable,
            preventExtensions: error_immutable,
            set: error_immutable,
            setPrototypeOf: error_immutable,
        });
    }

    return module;
}

function template_stub({filename, actual_render}) {
    return function render(...args) {
        // If our template was not mocked or is being rendered as a
        // partial, use the actual implementation.
        if (!template_mocks.has(filename) || in_mid_render) {
            return actual_render(...args);
        }

        used_templates.add(filename);

        const {exercise_template, f} = template_mocks.get(filename);

        const data = args[0];

        if (exercise_template) {
            // If our dev wants to exercise the actual template, then do so.
            // We set the in_mid_render bool so that included (i.e. partial)
            // templates get rendered.
            in_mid_render = true;
            const html = actual_render(...args);
            in_mid_render = false;

            return f(data, html);
        }

        return f(data);
    };
}

exports.start = () => {
    assert.equal(actual_load, undefined, "namespace.start was called twice in a row.");
    actual_load = Module._load;
    Module._load = load;
};

// We provide `mock_cjs` for mocking a CommonJS module, and `mock_esm` for
// mocking an ES6 module.
//
// A CommonJS module:
// - loads other modules using `require()`,
// - assigns its public contents to the `exports` object or `module.exports`,
// - consists of a single JavaScript value, typically an object or function,
// - when imported by an ES6 module:
//   * is shallow-copied to a collection of immutable bindings, if it's an
//     object,
//   * is converted to a single default binding, if not.
//
// An ES6 module:
// - loads other modules using `import`,
// - declares its public contents using `export` statements,
// - consists of a collection of live bindings that may be mutated from inside
//   but not outside the module,
// - may have a default binding (that's just syntactic sugar for a binding
//   named `default`),
// - when required by a CommonJS module, always appears as an object.
//
// Most of our own modules are ES6 modules.
//
// For a third party module available in both formats that might present two
// incompatible APIs (especially if the CommonJS module is a function),
// Webpack will prefer the ES6 module if its availability is indicated by the
// "module" field of package.json, while Node.js will not; we need to mock the
// format preferred by Webpack.

exports.mock_cjs = (module_path, obj, {callsite = callsites()[1]} = {}) => {
    assert.notEqual(
        module_path,
        "jquery",
        "We automatically mock jquery to zjquery. Grep for mock_jquery if you want more control.",
    );

    const filename = Module._resolveFilename(
        module_path,
        require.cache[callsite.getFileName()],
        false,
    );

    assert.ok(!module_mocks.has(filename), `You already set up a mock for ${filename}`);

    assert.ok(
        !(filename in require.cache),
        `It is too late to mock ${filename}; call this earlier.`,
    );

    module_mocks.set(filename, obj);
    return obj;
};

exports.mock_jquery = ($) => {
    jquery_function = $; // eslint-disable-line no-jquery/variable-pattern
    return $;
};

exports._start_template_mocking = () => {
    template_mocks.clear();
    used_templates.clear();
};

exports._finish_template_mocking = () => {
    for (const filename of template_mocks.keys()) {
        assert.ok(
            used_templates.has(filename),
            `You called mock_template with ${filename} but we never saw it get used.`,
        );
    }
    template_mocks.clear();
    used_templates.clear();
};

exports._mock_template = (fn, exercise_template, f) => {
    template_mocks.set(path.join(template_path, fn), {exercise_template, f});
};

exports.mock_esm = (module_path, obj = {}, {callsite = callsites()[1]} = {}) => {
    assert.equal(typeof obj, "object", "An ES module must be mocked with an object");
    return exports.mock_cjs(module_path, {...obj, __esModule: true}, {callsite});
};

exports.unmock_module = (module_path, {callsite = callsites()[1]} = {}) => {
    const filename = Module._resolveFilename(
        module_path,
        require.cache[callsite.getFileName()],
        false,
    );

    assert.ok(module_mocks.has(filename), `Cannot unmock ${filename}, which was not mocked`);

    assert.ok(
        used_module_mocks.has(filename),
        `You asked to mock ${filename} but we never saw it during compilation.`,
    );

    module_mocks.delete(filename);
    used_module_mocks.delete(filename);
};

exports.set_global = function (name, val) {
    assert.notEqual(val, null, `We try to avoid using null in our codebase.`);

    if (!(name in old_globals)) {
        if (!(name in global)) {
            new_globals.add(name);
        }
        old_globals[name] = global[name];
    }
    global[name] = val;
    return val;
};

exports.zrequire = function (short_fn) {
    assert.notEqual(
        short_fn,
        "templates",
        `
            There is no need to zrequire templates.ts.

            The test runner automatically registers the
            Handlebars extensions.
        `,
    );

    return require(`../../src/${short_fn}`);
};

const webPath = path.resolve(__dirname, "../..") + path.sep;
const testsLibPath = __dirname + path.sep;

exports.complain_about_unused_mocks = function () {
    for (const filename of module_mocks.keys()) {
        /* istanbul ignore if */
        if (!used_module_mocks.has(filename)) {
            console.error(`You asked to mock ${filename} but we never saw it during compilation.`);
        }
    }
};

exports.finish = function () {
    /*
        Handle cleanup tasks after we've run one module.

        Note that we currently do lazy compilation of modules,
        so we need to wait till the module tests finish
        running to do things like detecting pointless mocks
        and resetting our _load hook.
    */
    jquery_function = undefined;

    assert.notEqual(actual_load, undefined, "namespace.finish was called without namespace.start.");
    Module._load = actual_load;
    actual_load = undefined;

    module_mocks.clear();
    used_module_mocks.clear();

    for (const path of Object.keys(require.cache)) {
        if (path.startsWith(webPath) && !path.startsWith(testsLibPath)) {
            // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
            delete require.cache[path];
        }
    }
    Object.assign(global, old_globals);
    old_globals = {};
    for (const name of new_globals) {
        // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
        delete global[name];
    }
    new_globals.clear();
};

exports.with_overrides = function (test_function) {
    // This function calls test_function() and passes in
    // a way to override the namespace temporarily.

    const restore_callbacks = [];
    let ok = false;

    const override = function (obj, prop, value, {unused = true} = {}) {
        // Given an object `obj` (which is usually a module object),
        // we re-map `obj[prop]` to the `value` passed in by the caller.
        // Then the outer function here (`with_overrides`) automatically
        // restores the original value of `obj[prop]` as its last
        // step.  Generally our code calls `run_test`, which wraps
        // `with_overrides`.

        assert.ok(
            typeof obj === "object" || typeof obj === "function",
            `We cannot override a function for ${typeof obj} objects`,
        );

        const had_value = Object.hasOwn(obj, prop);
        const old_value = obj[prop];
        let new_value = value;

        if (typeof value === "function") {
            assert.ok(
                old_value === undefined || typeof old_value === "function",
                `
                    You are overriding a non-function with a function.
                    This is almost certainly an error.
                `,
            );

            new_value = function (...args) {
                unused = false;
                return value.apply(this, args);
            };

            // Let zjquery know this function was patched with override,
            // so it doesn't complain about us modifying it.  (Other
            // code can also use this, as needed.)
            new_value._patched_with_override = true;
        } else {
            unused = false;
        }

        obj[prop] = new_value;
        restore_callbacks.push(() => {
            if (ok) {
                assert.ok(!unused, `${prop} never got invoked!`);
            }
            if (had_value) {
                obj[prop] = old_value;
            } else {
                // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
                delete obj[prop];
            }
        });
    };

    const disallow = function (obj, prop) {
        override(
            obj,
            prop,
            // istanbul ignore next
            () => {
                throw new Error(`unexpected call to ${prop}`);
            },
            {unused: false},
        );
    };

    const override_rewire = function (obj, prop, value, {unused = true} = {}) {
        assert.ok(
            typeof obj === "object" || typeof obj === "function",
            `We cannot override a function for ${typeof obj} objects`,
        );

        assert.ok(Object.hasOwn(obj, prop));
        const old_value = obj[prop];
        let new_value = value;

        if (typeof value === "function") {
            assert.ok(
                typeof old_value === "function",
                `
                    You are overriding a non-function with a function.
                    This is almost certainly an error.
                `,
            );

            new_value = function (...args) {
                unused = false;
                return value.apply(this, args);
            };
        } else {
            unused = false;
        }

        const rewire_prop = `rewire_${prop}`;
        /* istanbul ignore if */
        if (!(rewire_prop in obj)) {
            assert.fail(`You must define ${rewire_prop} to use override_rewire on ${prop}.`);
        }
        obj[rewire_prop](new_value);
        restore_callbacks.push(() => {
            if (ok) {
                assert.ok(!unused, `${prop} never got invoked!`);
            }
            obj[rewire_prop](old_value);
        });
    };

    const disallow_rewire = function (obj, prop) {
        override_rewire(
            obj,
            prop,
            // istanbul ignore next
            () => {
                throw new Error(`unexpected call to ${prop}`);
            },
            {unused: false},
        );
    };

    let ret;
    let is_promise = false;
    try {
        ret = test_function({override, override_rewire, disallow, disallow_rewire});
        is_promise = typeof ret?.then === "function";
        ok = !is_promise;
    } finally {
        if (!is_promise) {
            restore_callbacks.reverse();
            for (const restore_callback of restore_callbacks) {
                restore_callback();
            }
        }
    }

    if (!is_promise) {
        return ret;
    }

    return (async () => {
        try {
            ret = await ret;
            ok = true;
            return ret;
        } finally {
            restore_callbacks.reverse();
            for (const restore_callback of restore_callbacks) {
                restore_callback();
            }
        }
    })();
};
