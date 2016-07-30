var render = (function () {

var exports = {};

var fs = require('fs');
var _ = require('third/underscore/underscore.js');
var Handlebars = require('handlebars');

function template_dir() {
    return __dirname + '/../../static/templates/';
}

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
    var data = fs.readFileSync(template_dir() + name + '.handlebars').toString();
    Handlebars.templates[name] = Handlebars.compile(data);
};

return exports;
}());
module.exports = render;

