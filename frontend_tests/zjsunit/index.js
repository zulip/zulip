global.assert = require('assert');
require('node_modules/string.prototype.codepointat/codepointat.js');

global.Dict = require('js/dict');
global._ = require('node_modules/underscore/underscore.js');
var _ = global._;

// Find the files we need to run.
var finder = require('./finder.js');
var files = finder.find_files_to_run(); // may write to console
if (_.isEmpty(files)) {
    throw "No tests found";
}

// Set up our namespace helpers.
var namespace = require('./namespace.js');
global.set_global = namespace.set_global;
global.patch_builtin = namespace.patch_builtin;
global.add_dependencies = namespace.add_dependencies;
global.stub_out_jquery = namespace.stub_out_jquery;
global.with_overrides = namespace.with_overrides;

// Set up stub helpers.
var stub = require('./stub.js');
global.with_stub = stub.with_stub;

// Set up helpers to render templates.
var render = require('./render.js');
global.make_sure_all_templates_have_been_compiled =
    render.make_sure_all_templates_have_been_compiled;
global.find_included_partials = render.find_included_partials;
global.compile_template = render.compile_template;
global.render_template = render.render_template;
global.walk = render.walk;

// Set up helpers to output HTML
var output = require('./output.js');
global.write_handlebars_output = output.write_handlebars_output;
global.write_test_output = output.write_test_output;
global.append_test_output = output.append_test_output;

var noop = function () {};

output.start_writing();

files.forEach(function (file) {
    global.patch_builtin('setTimeout', noop);
    global.patch_builtin('setInterval', noop);

    console.info('running tests for ' + file.name);
    render.init();
    require(file.full_name);
    namespace.restore();
});

console.info("To see more output, open " + output.index_fn);
