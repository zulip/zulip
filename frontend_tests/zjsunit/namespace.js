var namespace = (function () {

var _ = require('underscore/underscore.js');
var exports = {};

var dependencies = [];
var old_builtins = {};

// Set this just before we execute the tests in index.js
exports.base_requires = undefined;

exports.set_global = function (name, val) {
    global[name] = val;
    dependencies.push(name);
    return val;
};

exports.patch_builtin = function (name, val) {
    old_builtins[name] = global[name];
    global[name] = val;
    return val;
};

function resolve_name(name, fn) {
    if (fn === undefined) {
        fn = '../../static/js/' + name;
    } else if (/generated\/|js\/|third\//.test(fn)) {
        // FIXME: Stealing part of the NPM namespace is confusing.
        fn = '../../static/' + fn;
    }
    return fn;
}

// Require a module and get a handle to it for monkey patching.
// Can not patch if module.exports is not an object (only objects are passed by
// reference) or the module is imported with ES6's import statement (it has a
// separate cache).
// Put this before other zrequire-s if you run into caching issues.
exports.zrequire_pure = function (name, fn) {
    fn = resolve_name(name, fn);
    return require(fn);
};

exports.zrequire = function (name, fn) {
    var obj = exports.zrequire_pure(name, fn);
    set_global(name, obj);
    return obj;
};

// Completely stub out a module. Return a handle for further patching.
exports.zstub = function (name, fn, stub) {
    fn = resolve_name(name, fn);
    const path = require.resolve(fn);
    require.cache[path] = {
        id: path,
        filename: path,
        loaded: true,
        exports: stub,
    };
    return require(fn);
};

exports.restore = function () {
    dependencies.forEach(function (name) {
        delete global[name];
    });
    dependencies = [];
    for (const key of Object.keys(require.cache)) {
        if (!exports.base_requires.has(key)) {
            delete require.cache[key];
        }
    }
    delete global.window.electron_bridge;
    _.extend(global, old_builtins);
    old_builtins = {};
};

exports.stub_out_jquery = function () {
    set_global('$', function () {
        return {
            on: function () {},
            trigger: function () {},
            hide: function () {},
            removeClass: function () {},
        };
    });
    $.fn = {};
    $.now = function () {};
};

exports.with_overrides = function (test_function) {
    // This function calls test_function() and passes in
    // a way to override the namespace temporarily.

    var clobber_callbacks = [];

    var override = function (name, f) {
        var parts = name.split('.');
        var module = parts[0];
        var func_name = parts[1];

        if (!_.has(global, module)) {
            set_global(module, {});
        }

        global[module][func_name] = f;

        clobber_callbacks.push(function () {
            // If you get a failure from this, you probably just
            // need to have your test do its own overrides and
            // not cherry-pick off of the prior test's setup.
            global[module][func_name] =
                'ATTEMPTED TO REUSE OVERRIDDEN VALUE FROM PRIOR TEST';
        });
    };

    test_function(override);

    _.each(clobber_callbacks, function (f) {
        f();
    });
};



return exports;
}());
module.exports = namespace;
