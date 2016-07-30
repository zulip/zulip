global.assert = require('assert');
var fs = require('fs');
var path = require('path');
require('third/string-prototype-codepointat/codepointat.js');

global.Dict = require('js/dict');
global._ = require('third/underscore/underscore.js');
var _ = global._;

// Set up our namespace helpers.
var namespace = require('./namespace.js');
global.set_global = namespace.set_global;
global.patch_builtin = namespace.patch_builtin;
global.add_dependencies = namespace.add_dependencies;

// Set up helpers to render templates.
var render = require('./render.js');
global.use_template = render.use_template;
global.make_sure_all_templates_have_been_compiled = render.make_sure_all_templates_have_been_compiled;

// Set up helpers to output HTML
var output = require('./output.js');
global.write_handlebars_output = output.write_handlebars_output;
global.write_test_output = output.write_test_output;
global.append_test_output = output.append_test_output;

// Run all the JS scripts in our test directory.  Tests do NOT run
// in isolation.

var oneFileFilter = [];
var testsDifference = [];
if (process.argv[2] ) {
    oneFileFilter = process.argv
      .slice(2)
      .map(function (filename) {return filename.replace(/\.js$/i, '');});
}

// tests_dir is where we find our specific unit tests (as opposed
// to framework code)
var tests_dir = __dirname.replace(/zjsunit/, 'node_tests');

var tests = fs.readdirSync(tests_dir)
  .filter(function (filename) {return (/\.js$/i).test(filename);})
  .map(function (filename) {return filename.replace(/\.js$/i, '');});

if (oneFileFilter.length > 0) {
    tests = tests.filter(function (filename) {
        return oneFileFilter.indexOf(filename) !== -1;
    });
    testsDifference = _.difference(oneFileFilter, tests);
}
tests.sort();

output.start_writing();

tests.forEach(function (filename) {
    console.info('running tests for ' + filename);
    require(path.join(tests_dir, filename));
    namespace.restore();
});

if (oneFileFilter.length > 0 && testsDifference.length > 0) {
    testsDifference.forEach(function (filename) {
        console.log(filename + " does not exist");
    });
    if (oneFileFilter.length > testsDifference.length) {
        console.info("To see more output, open " + output.index_fn);
    }
} else {
    console.info("To see more output, open " + output.index_fn);
}
