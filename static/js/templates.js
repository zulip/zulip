var templates = (function () {

var exports = {};

exports.render = function (name, arg) {
    if (Handlebars.templates === undefined) {
        Handlebars.templates = {};
    }

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

// We don't want to wait for DOM ready to register the Handlebars helpers
// below. There's no need to, as they do not access the DOM.
// Furthermore, waiting for DOM ready would introduce race conditions with
// other DOM-ready callbacks that attempt to render templates.

// Regular Handlebars partials require pre-registering.  This allows us
// to treat any template as a partial.
Handlebars.registerHelper('partial', function (template_name, context) {
    return new Handlebars.SafeString(exports.render(template_name, this));
});

Handlebars.registerHelper('plural', function (condition, one, other) {
    return (condition === 1) ? one : other;
});

Handlebars.registerHelper('if_and', function () {
    // Execute the conditional code if all conditions are true.
    // Example usage:
    //     {{#if_and cond1 cond2 cond3}}
    //         <p>All true</p>
    //     {{/if_and}}
    var options = arguments[arguments.length - 1];
    var i;
    for (i = 0; i < arguments.length - 1; i++) {
        if (!arguments[i]) {
            return options.inverse(this);
        }
    }
    return options.fn(this);
});

return exports;
}());
