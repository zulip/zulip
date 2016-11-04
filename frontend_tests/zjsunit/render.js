var render = (function () {

var exports = {};

var fs = require('fs');
var path = require("path");
var _ = require('third/underscore/underscore.js');
var Handlebars = require('handlebars');

function template_dir() {
    return __dirname + '/../../static/templates/';
}

var list_of_exceptions = [""].concat((function () {
    return fs.readdirSync(template_dir()).filter(function (file) {
        return fs.statSync(path.join(template_dir(), file)).isDirectory();
    });
}()));

exports.init = function () {
    Handlebars.templates = {};
};

exports.make_sure_all_templates_have_been_compiled = function () {
    var dir = template_dir();
    var fns = fs.readdirSync(dir).filter(function (fn) {
        return (/\.handlebars/).test(fn);
    });

    _.each(fns, function (fn) {
        var name = fn.split('.')[0];
        if (!Handlebars.templates[name]) {
            throw "The file " + fn + " has no test coverage.";
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

    var flag = false,
        counter = 0,
        data;

    while (flag === false && counter < list_of_exceptions.length) {
        try {
            data = fs.readFileSync(path.join(template_dir(), list_of_exceptions[counter], name + '.handlebars')).toString();
            if (data) {
                flag = true;
            }
        } catch (err) {
            flag = false;
        } finally {
            counter++;
        }
    }

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
                name: file
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
    var files = exports.walk(template_dir()).map(function (file) {
        return {
            url: file.url,
            name: file.name.replace(/\.handlebars$/, "")
        };
    });

    self.get = function (name) {
        var file = files.find(function (file) {
            return file.name === name;
        });
        assert(file);

        return file;
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
