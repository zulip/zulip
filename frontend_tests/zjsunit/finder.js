const _ = require("underscore/underscore.js");
const fs = require("fs");
const path = require("path");

exports.find_files_to_run = function () {
    let oneFileFilter = [];
    let testsDifference = [];
    if (process.argv[2]) {
        oneFileFilter = process.argv
            .slice(2)
            .filter((filename) => /[.]js$/.test(filename))
            .map((filename) => filename.replace(/\.js$/i, ""));
    }

    // tests_dir is where we find our specific unit tests (as opposed
    // to framework code)
    const tests_dir = __dirname.replace(/zjsunit/, "node_tests");

    let tests = fs
        .readdirSync(tests_dir)
        .filter((filename) => !/^\./i.test(filename))
        .filter((filename) => /\.js$/i.test(filename))
        .map((filename) => filename.replace(/\.js$/i, ""));

    if (oneFileFilter.length > 0) {
        tests = tests.filter((filename) => oneFileFilter.includes(filename));
        testsDifference = _.difference(oneFileFilter, tests);
    }

    testsDifference.forEach((filename) => {
        throw filename + ".js does not exist";
    });

    tests.sort();

    const files = tests.map((fn) => {
        const obj = {};
        obj.name = fn;
        obj.full_name = path.join(tests_dir, fn);
        return obj;
    });

    return files;
};
