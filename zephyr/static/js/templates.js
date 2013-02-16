var templates = (function () {

var exports = {};

exports.render = function (name, arg) {
    if (Handlebars.templates === undefined)
        Handlebars.templates = {};

    if (Handlebars.templates[name] === undefined) {
        // Fetch the template using a synchronous AJAX request.
        //
        // This is only for local development.  In prod we precompile
        // templates and serve JavaScript which will have already
        // populated Handlebars.templates.
        $.ajax({
            url:     '/static/templates/'+name+'.handlebars',
            async:   false,
            success: function (data) {
                Handlebars.templates[name] = Handlebars.compile(data);
            }
        });
    }

    return Handlebars.templates[name](arg);
};

return exports;
}());
