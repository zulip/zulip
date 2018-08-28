var finder = (function () {

var exports = {};

var _ = require('node_modules/underscore/underscore.js');
var fs = require('fs');
var path = require('path');

exports.find_files_to_run = function () {
    var oneFileFilter = [];
    var testsDifference = [];
    if (process.argv[2]) {
        oneFileFilter = process.argv
            .slice(2)
            .filter(function (filename) {return (/[.]js$/).test(filename);})
            .map(function (filename) {return filename.replace(/\.js$/i, '');});
    }

    // tests_dir is where we find our specific unit tests (as opposed
    // to framework code)
    var tests_dir = __dirname.replace(/zjsunit/, 'node_tests');

    var tests = fs.readdirSync(tests_dir)
        .filter(function (filename) {return !(/^\./i).test(filename);})
        .filter(function (filename) {return (/\.js$/i).test(filename);})
        .map(function (filename) {return filename.replace(/\.js$/i, '');});

    if (oneFileFilter.length > 0) {
        tests = tests.filter(function (filename) {
            return oneFileFilter.indexOf(filename) !== -1;
        });
        testsDifference = _.difference(oneFileFilter, tests);
    }

    testsDifference.forEach(function (filename) {
        throw filename + ".js does not exist";
    });

    tests.sort();

    var files = tests.map(function (fn) {
        var obj = {};
        obj.name = fn;
        obj.full_name = path.join(tests_dir, fn);
        return obj;
    });

    return files;
};


return exports;
}());
module.exports = finder;
