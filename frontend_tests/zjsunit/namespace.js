var namespace = (function () {

var _ = require('third/underscore/underscore.js');
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

return exports;
}());
module.exports = namespace;
