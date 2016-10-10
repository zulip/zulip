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

fs.readdirSync(path.join(__dirname, "../../static/templates/", "settings")).forEach(function (o) {
    exports.use_template(o.replace(/\.handlebars/, ""));
});

return exports;
}());
module.exports = render;
