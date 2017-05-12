var namespace = (function () {

var _ = require('node_modules/underscore/underscore.js');
var exports = {};

var dependencies = [];
var requires = [];
var old_builtins = {};

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

exports.add_dependencies = function (dct) {
    _.each(dct, function (fn, name) {
        var obj = require(fn);
        requires.push(fn);
        set_global(name, obj);
    });
};

exports.restore = function () {
    dependencies.forEach(function (name) {
        delete global[name];
    });
    requires.forEach(function (fn) {
        delete require.cache[require.resolve(fn)];
    });
    dependencies = [];
    _.extend(global, old_builtins);
    old_builtins = {};
};

exports.stub_out_jquery = function () {
    set_global('$', function () {
        return {
            on: function () {},
            trigger: function () {},
            hide: function () {},
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
