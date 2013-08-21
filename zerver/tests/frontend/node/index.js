var fs = require('fs');
var _ = require('third/underscore/underscore.js');

// Run all the JS scripts in our test directory.  Tests do NOT run
// in isolation.

var tests = fs.readdirSync(__dirname)
    .filter(function (filename) { return (/\.js$/i).test(filename); })
    .map(function (filename) { return filename.replace(/\.js$/i, ''); });

var dependencies = [];

global.set_global = function (name, val) {
    global[name] = val;
    dependencies.push(name);
    return val;
};

global.add_dependencies = function (dct) {
    _.each(dct, function (fn, name) {
        var obj = require(fn);
        set_global(name, obj);
    });
};

tests.forEach(function (filename) {
    if (filename === 'index') {
        return;
    }
    console.info('running tests for ' + filename);
    require('./' + filename);

    dependencies.forEach(function (name) {
        delete global[name];
    });
    dependencies = [];
});
