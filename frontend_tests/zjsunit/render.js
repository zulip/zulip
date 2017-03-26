var render = (function () {

var exports = {};

var fs = require('fs');
var _ = require('node_modules/underscore/underscore.js');
var Handlebars = require('handlebars');

function template_dir() {
    return __dirname + '/../../static/templates/';
}

exports.init = function () {
    Handlebars.templates = {};
};

exports.make_sure_all_templates_have_been_compiled = function () {
    var files = exports.template_finder.get_all();

    _.each(files, function (file) {
        if (!Handlebars.templates[file.name]) {
            throw "The file " + file.url + " has no test coverage.";
        }
    });
};

exports.render_template = function (name, args) {
    exports.compile_template(name);
    return global.templates.render(name, args);
};

exports.compile_template = function (name) {
    var included_fns = exports.find_included_partials(name);

    _.each(included_fns, function (fn) {
        exports.compile_template(fn);
    });

    if (Handlebars.templates === undefined) {
        Handlebars.templates = {};
    }

    if (_.has(Handlebars.template, name)) {
        // we already compile the template
        return;
    }

    var file = exports.template_finder.get(name);
    var data = fs.readFileSync(file.url).toString();
    Handlebars.templates[name] = Handlebars.compile(data);
};

// list all files in a directory and it's subdirectories in a recursive sync way.
exports.walk = function (dir, filelist) {
    filelist = filelist || [];

    // grab files one level deep.
    var files = fs.readdirSync(dir);

    // for each file, check if it's a directory. If so, continue recursion.
    // if not add to the file list.
    files.forEach(function (file) {
        if (fs.statSync(dir + "/" + file).isDirectory()) {
            filelist = exports.walk(dir + "/" + file, filelist);
        } else {
            filelist.push({
                url: dir + "/" + file,
                name: file,
            });
        }
    });

    // return all recursively found files.
    return filelist;
};

exports.template_finder = (function () {
    // This class lets you find template files in our file system.
    // It may be slightly overkill for our flat directory system;
    // it might make more sense to just do something more like
    // this: get_template_dir() + name + '.handlebars'

    var self = {};

    // get all files and then map them into friendlier names.
    var all_files = exports.walk(template_dir());
    var files = all_files
            .filter(function (file) {
                return (/\.handlebars$/).test(file.name);
            })
            .map(function (file) {
                return {
                    url: file.url,
                    name: file.name.replace(/\.handlebars$/, ""),
                };
            });

    self.get = function (name) {
        var file = files.find(function (file) {
            return file.name === name;
        });
        assert(file);

        return file;
    };

    self.get_all = function () {
        return files;
    };

    return self;
}());

exports.find_included_partials = function (name) {

    var file = exports.template_finder.get(name);

    assert(file);

    var template = fs.readFileSync(file.url, "utf8");

    var lst = [];

    // match partial tags.
    // this uses String.prototype.replace which is kind of hacky but
    // it is the only JS function IIRC that allows you to match all
    // instances of a pattern AND return capture groups.
    template.replace(/\{\{\s*partial\s*"(.+?)"/ig, function (match, $1) {
        lst.push($1);
    });

    return lst;
};

return exports;
}());
module.exports = render;
