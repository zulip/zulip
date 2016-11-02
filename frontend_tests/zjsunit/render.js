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

exports.use_template = function (name) {
    if (Handlebars.templates === undefined) {
        Handlebars.templates = {};
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

exports.partial_finder = (function () {
    var meta = {
        read: []
    };

    // get all files and then map them into friendlier names.
    var files = exports.walk(path.join(__dirname, "../../static/templates")).map(function (file) {
        return {
            url: file.url,
            name: file.name.replace(/\.handlebars$/, "")
        };
    });

    // this is the external function that is called that will recursively search
    // for partials in a file and partials inside partials until it finds them all.
    // it then adds them to a maintenance list of already read partials so that
    // they don't have to be read/searched again.
    var __prototype__ = function (name, callback) {
        if (meta.read.indexOf(name) === -1) {
            if (callback) {
                callback(name);
            }

            meta.read.push(name);

            var file = files.find(function (file) {
                return file.name === name;
            });

            if (file) {
                var template = fs.readFileSync(file.url, "utf8");

                // match partial tags.
                // this uses String.prototype.replace which is kind of hacky but
                // it is the only JS function IIRC that allows you to match all
                // instances of a pattern AND return capture groups.
                template.replace(/\{\{\s*partial\s*"(.+?)"/ig, function (match, $1) {
                    __prototype__($1, callback);
                });
            }
        }
    };

    return __prototype__;
}());

fs.readdirSync(path.join(__dirname, "../../static/templates/", "settings")).forEach(function (o) {
    exports.use_template(o.replace(/\.handlebars/, ""));
});

return exports;
}());
module.exports = render;
