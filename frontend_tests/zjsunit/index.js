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

function stylesheets() {
    // TODO: Automatically get all relevant styles.
    var data = '';
    data += '<link href="../../static/styles/fonts.css" rel="stylesheet">\n';
    data += '<link href="../../static/styles/portico.css" rel="stylesheet">\n';
    data += '<link href="../../static/styles/thirdparty-fonts.css" rel="stylesheet">\n';
    data += '<link href="../../static/styles/zulip.css" rel="stylesheet">\n';
    data += '<link href="../../static/third/bootstrap/css/bootstrap.css" rel="stylesheet">\n';
    data += '<link href="../../static/third/bootstrap-notify/css/bootstrap-notify.css" rel="stylesheet">\n';

    return data;
}

var mkdir_p = function (path) {
    // This works like mkdir -p in Unix.
    try {
        fs.mkdirSync(path);
    } catch(e) {
        if ( e.code !== 'EEXIST' ) {
            throw e;
        }
    }
    return path;
};

var output_dir = (function () {
    mkdir_p('var');
    var dir = mkdir_p('var/test-js-with-node');
    return dir;
}());

var output_fn = path.join(output_dir, 'output.html');
var index_fn = path.join(output_dir, 'index.html');

(function () {
    var data = '';

    data += stylesheets();
    data += '<style type="text/css">.collapse {height: inherit}</style>\n';
    data += '<style type="text/css">body {width: 500px; margin: auto; overflow: scroll}</style>\n';
    data += '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">';
    data += '<h1>Output of node unit tests</h1>\n';
    fs.writeFileSync(output_fn, data);

    data = '';
    data += '<style type="text/css">body {width: 500px; margin: auto; overflow: scroll}</style>\n';
    data += '<h2>Regular output</h2>\n';
    data += '<p>Any test can output HTML to be viewed here:</p>\n';
    data += '<a href="output.html">Output of non-template.js tests</a><br />';
    data += '<hr />\n';
    data += '<h2>Handlebar output</h2>\n';
    data += '<p>These are specifically from templates.js</p>\n';
    fs.writeFileSync(index_fn, data);
}());

global.write_test_output = function (label, output) {
    var data = '';

    data += '<hr>';
    data += '<h3>' + label + '</h3>';
    data += output;
    data += '\n';
    fs.appendFileSync(output_fn, data);
};

global.write_handlebars_output = (function () {
    var last_label = '';

    return function (label, output) {
        if (last_label && (last_label >= label)) {
            // This is kind of an odd requirement, but it allows us
            // to render output on the fly in alphabetical order, and
            // it has a nice side effect of making our source code
            // easier to scan.

            console.info(last_label);
            console.info(label);
            throw "Make sure your template tests are alphabetical in templates.js";
        }
        last_label = label;

        var href = label + '.handlebars.html';
        var fn = path.join(output_dir, href);

        // Update the index
        var a = '<a href="' + href +  '">' + label + '</a><br />';
        fs.appendFileSync(index_fn, a);

        // Write out own HTML file.
        var data = '';
        data += stylesheets();
        data += '<style type="text/css">body {width: 500px; margin: auto; overflow: scroll}</style>\n';
        data += '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">';
        data += '<b>' + href + '</b><hr />\n';
        data += output;
        fs.writeFileSync(fn, data);
    };
}());

global.append_test_output = function (output) {
    fs.appendFileSync(output_fn, output);
};

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
        console.info("To see more output, open " + index_fn);
    }
} else {
    console.info("To see more output, open " + index_fn);
}
