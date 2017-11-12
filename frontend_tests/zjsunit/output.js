var output = (function () {

var exports = {};

var fs = require('fs');
var path = require('path');

function mkdir_p(path) {
    // This works like mkdir -p in Unix.
    try {
        fs.mkdirSync(path);
    } catch (e) {
        if (e.code !== 'EEXIST') {
            throw e;
        }
    }
    return path;
}

function make_output_dir() {
    mkdir_p('var');
    var dir = mkdir_p('var/test-js-with-node');
    return dir;
}

// TODO, move these actions with side effects to some kind
//       of init() function.
var output_dir = make_output_dir();
var output_fn = path.join(output_dir, 'output.html');
var index_fn = path.join(output_dir, 'index.html');

exports.index_fn = index_fn;

function stylesheets() {
    // TODO: Automatically get all relevant styles.
    //       Note that we specifically do NOT use media.css here,
    //       since we are focused on showing components in isolation.
    var data = '';
    data += '<link href="../../static/styles/fonts.css" rel="stylesheet">\n';
    data += '<link href="../../static/styles/portico.css" rel="stylesheet">\n';
    data += '<link href="../../static/third/thirdparty-fonts.css" rel="stylesheet">\n';
    data += '<link href="../../static/generated/icons/style.css" rel="stylesheet">\n';
    data += '<link href="../../static/styles/zulip.css" rel="stylesheet">\n';
    data += '<link href="../../static/styles/settings.css" rel="stylesheet">\n';
    data += '<link href="../../static/styles/left-sidebar.css" rel="stylesheet">\n';
    data += '<link href="../../static/third/bootstrap/css/bootstrap.css" rel="stylesheet">\n';
    data += '<link href="../../static/third/bootstrap-notify/css/bootstrap-notify.css" rel="stylesheet">\n';

    return data;
}

exports.start_writing = function () {
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
};


exports.write_test_output = function (label, output) {
    var data = '';

    data += '<hr>';
    data += '<h3>' + label + '</h3>';
    data += output;
    data += '\n';
    fs.appendFileSync(output_fn, data);
};

exports.write_handlebars_output = (function () {
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

exports.append_test_output = function (output) {
    fs.appendFileSync(output_fn, output);
};


return exports;
}());
module.exports = output;
