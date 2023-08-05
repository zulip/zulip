"use strict";

const {strict: assert} = require("assert");
const Module = require("module");
const path = require("path");

const callsites = require("callsites");

const $ = require("./zjquery");

const new_globals = new Set();
let old_globals = {};

let actual_load;
const module_mocks = new Map();
const template_mocks = new Map();
const used_module_mocks = new Set();
const used_templates = new Set();

const jquery_path = require.resolve("jquery");
const real_jquery_path = require.resolve("./real_jquery.js");

let in_mid_render = false;
let jquery_function;

const template_path = path.resolve(__dirname, "../../templates");

/* istanbul ignore next */
function need_to_mock_template_error(filename) {
    const fn = path.relative(template_path, filename);

    return `
        Please use mock_template if your test needs to render ${fn}

        We use mock_template in our unit tests to verify that the
        JS code is calling the template with the proper data. And
        then we use the results of mock_template to supply the JS
        code with either the actual HTML from the template or some
        kind of zjquery stub.

        The basic pattern is this (grep for mock_template to see real
        world examples):

        run_test("test something calling template", ({mock_template}) => {
            // We encourage you to set the second argument to false
            // if you are not actually inspecting or using the results
            // of actually rendering the template.
            mock_template("${fn}", false, (data) => {
                assert.deepEqual(data, {...};
                // or assert more specific things about the data
                return "stub-for-zjquery";
            });

            // If you need the actual HTML from the template, do
            // something like below instead. (We set the second argument
            // to true which tells mock_template that is should call
            // the actual template rendering function and pass in the
            // resulting html to us.
            mock_template("${fn}", true, (data, html) => {
                assert.deepEqual(data, {...};
                assert.ok(html.startWith(...));
                return html;
            });
        });
    `;
}

function load(request, parent, isMain) {
    const filename = Module._resolveFilename(request, parent, isMain);
    if (module_mocks.has(filename)) {
        used_module_mocks.add(filename);
        const obj = module_mocks.get(filename);
        return obj;
    }

    if (filename.endsWith(".hbs") && filename.startsWith(template_path + path.sep)) {
        const actual_render = actual_load(request, parent, isMain);

        return template_stub({filename, actual_render});
    }

    if (filename === jquery_path && parent.filename !== real_jquery_path) {
        return jquery_function || $;
    }

    return actual_load(request, parent, isMain);
}

function template_stub({filename, actual_render}) {
    return function render(...args) {
        // If our template is being rendered as a partial, always
        // use the actual implementation.
        if (in_mid_render) {
            return actual_render(...args);
        }

        // Force devs to call mock_template on every top-level template
        // render so they can introspect the data.
        /* istanbul ignore if */
        if (!template_mocks.has(filename)) {
            throw new Error(need_to_mock_template_error(filename));
        }

        used_templates.add(filename);

        const {exercise_template, f} = template_mocks.get(filename);

        const data = args[0];

        if (exercise_template) {
            // If our dev wants to exercise the actual template, then do so.
            // We set the in_mid_render bool so that included (i.e partial)
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
            There is no need to zrequire templates.js.

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

        assert.ok(
            !("__esModule" in obj && "__Rewire__" in obj),
            "Cannot mutate an ES module from outside. Consider exporting a test helper function from it instead.",
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
        // This is deprecated because it relies on the slow
        // babel-plugin-rewire-ts plugin.  Consider alternatives such
        // as exporting a helper function for tests from the module
        // containing the function you need to mock.

        assert.ok(
            typeof obj === "object" || typeof obj === "function",
            `We cannot override a function for ${typeof obj} objects`,
        );

        // https://github.com/rosswarren/babel-plugin-rewire-ts/issues/15
        const old_value = prop in obj ? obj[prop] : obj.__GetDependency__(prop);
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

        obj.__Rewire__(prop, new_value);
        restore_callbacks.push(() => {
            if (ok) {
                assert.ok(!unused, `${prop} never got invoked!`);
            }
            obj.__Rewire__(prop, old_value);
        });
    };

    const disallow_rewire = function (obj, prop) {
        // This is deprecated because it relies on the slow
        // babel-plugin-rewire-ts plugin.

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
