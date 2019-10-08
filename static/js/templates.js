var templates = (function () {

var exports = {};

exports.render = function (name, arg) {
    if (Handlebars.templates === undefined) {
        throw new Error("Cannot find compiled templates!");
    }
    if (Handlebars.templates[name] === undefined) {
        throw new Error("Cannot find a template with this name: " + name
              + ". If you are developing a new feature, this likely "
              + "means you need to add the file static/templates/"
              + name + ".handlebars");
    }

    // The templates should be compiled into compiled.js.  In
    // prod we build compiled.js as part of the deployment process,
    // and for devs we have run_dev.py build compiled.js when templates
    // change.
    return Handlebars.templates[name](arg);
};

// We don't want to wait for DOM ready to register the Handlebars helpers
// below. There's no need to, as they do not access the DOM.
// Furthermore, waiting for DOM ready would introduce race conditions with
// other DOM-ready callbacks that attempt to render templates.

// Regular Handlebars partials require pre-registering.  This allows us to treat
// any template as a partial.  We also allow the partial to be passed additional
// named arguments.  Arguments should alternate between strings which will be
// used as the name and the associated value.
Handlebars.registerHelper('partial', function (template_name) {
    var extra_data = {};
    var args_len = arguments.length;
    var i;

    for (i = 1; i < args_len - 2; i += 2) {
        extra_data[arguments[i]] = arguments[i + 1];
    }
    var data = _.extend({}, this, extra_data);

    return new Handlebars.SafeString(exports.render(template_name, data));
});

Handlebars.registerHelper('plural', function (condition, one, other) {
    return condition === 1 ? one : other;
});

Handlebars.registerHelper('if_and', function () {
    // Execute the conditional code if all conditions are true.
    // Example usage:
    //     {{#if_and cond1 cond2 cond3}}
    //         <p>All true</p>
    //     {{/if_and}}
    var options = arguments[arguments.length - 1];
    var i;
    for (i = 0; i < arguments.length - 1; i += 1) {
        if (!arguments[i]) {
            return options.inverse(this);
        }
    }
    return options.fn(this);
});

Handlebars.registerHelper('unless_a_not_b', function () {
    // Execute the conditional code if at least one condition is false.
    // Example usage:
    //     {{#unless_a_not_b cond1 cond2}}
    //         <p>a is false or b is true</p>
    //     {{/unless_a_not_b}}
    var options = arguments[arguments.length - 1];
    if (arguments[0] && !arguments[1]) {
        return options.inverse(this);
    }
    return options.fn(this);
});

Handlebars.registerHelper('if_not_a_or_b_and_not_c', function () {
    var options = arguments[arguments.length - 1];
    if (arguments[0] === false || arguments[1] === true && arguments[2] === false) {
        return options.fn(this);
    }
    return options.inverse(this);
});

Handlebars.registerHelper('if_or', function () {
    // Execute the conditional code if any of the conditions are true.
    // Example usage:
    //     {{#if_or cond1 cond2 cond3}}
    //         <p>At least one is true</p>
    //     {{/if_or}}
    var options = arguments[arguments.length - 1];
    var i;
    for (i = 0; i < arguments.length - 1; i += 1) {
        if (arguments[i]) {
            return options.fn(this);

        }
    }
    return options.inverse(this);
});

Handlebars.registerHelper('is_false', function (variable, options) {
    if (variable === false) {
        return options.fn(this);
    }
    return options.inverse(this);
});

Handlebars.registerHelper('t', function (i18n_key) {
    // Marks a string for translation.
    // Example usage:
    //     {{t "some English text"}}
    var result = i18n.t(i18n_key);
    return new Handlebars.SafeString(result);
});

Handlebars.registerHelper('tr', function (context, options) {
    // Marks a block for translation.
    // Example usage 1:
    //     {{#tr context}}
    //         <p>some English text</p>
    //     {{/tr}}
    //
    // Example usage 2:
    //     {{#tr context}}
    //         <p>This __variable__ will get value from context</p>
    //     {{/tr}}
    //
    // Notes:
    //     1. `context` is very important. It can be `this` or an
    //        object or key of the current context.
    //     2. Use `__` instead of `{{` and `}}` to declare expressions
    var result = i18n.t(options.fn(context), context);
    return new Handlebars.SafeString(result);
});

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = templates;
}
window.templates = templates;
