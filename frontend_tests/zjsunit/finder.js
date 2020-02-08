const _ = require('underscore/underscore.js');
const fs = require('fs');
const path = require('path');

exports.find_files_to_run = function () {
    let oneFileFilter = [];
    let testsDifference = [];
    if (process.argv[2]) {
        oneFileFilter = process.argv
            .slice(2)
            .filter(function (filename) {return (/[.]js$/).test(filename);})
            .map(function (filename) {return filename.replace(/\.js$/i, '');});
    }

    // tests_dir is where we find our specific unit tests (as opposed
    // to framework code)
    const tests_dir = __dirname.replace(/zjsunit/, 'node_tests');

    let tests = fs.readdirSync(tests_dir)
        .filter(function (filename) {return !(/^\./i).test(filename);})
        .filter(function (filename) {return (/\.js$/i).test(filename);})
        .map(function (filename) {return filename.replace(/\.js$/i, '');});

    if (oneFileFilter.length > 0) {
        tests = tests.filter(function (filename) {
            return oneFileFilter.includes(filename);
        });
        testsDifference = _.difference(oneFileFilter, tests);
    }

    testsDifference.forEach(function (filename) {
        throw filename + ".js does not exist";
    });

    tests.sort();

    const files = tests.map(function (fn) {
        const obj = {};
        obj.name = fn;
        obj.full_name = path.join(tests_dir, fn);
        return obj;
    });

    return files;
};
