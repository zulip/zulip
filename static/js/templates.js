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
            url:     '/static/templates/'+name+'.handlebars?' + new Date().getTime(),
            async:   false,
            success: function (data) {
                Handlebars.templates[name] = Handlebars.compile(data);
            }
        });
    }

    return Handlebars.templates[name](arg);
};

$(function () {
    // Regular Handlebars partials require pre-registering.  This allows us
    // to treat any template as a partial.
    Handlebars.registerHelper('partial', function (template_name, context) {
        return new Handlebars.SafeString(exports.render(template_name, this));
    });
});

return exports;
}());
