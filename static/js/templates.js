// Below, we register Zulip-specific extensions to the handlebars API.
//
// IMPORTANT: When adding a new handlebars helper, update the
// knownHelpers array in the webpack config so that webpack knows your
// helper is registered at runtime and don't try to require them when
// bundling.

// We don't want to wait for DOM ready to register the Handlebars helpers
// below. There's no need to, as they do not access the DOM.
// Furthermore, waiting for DOM ready would introduce race conditions with
// other DOM-ready callbacks that attempt to render templates.

Handlebars.registerHelper('plural', function (condition, one, other) {
    return condition === 1 ? one : other;
});

Handlebars.registerHelper({
    eq: function (a, b) { return a === b; },
    and: function () {
        // last argument is Handlebars options
        if (arguments.length < 2) {
            return true;
        }
        var i;
        for (i = 0; i < arguments.length - 2; i += 1) {
            if (!arguments[i] || Handlebars.Utils.isEmpty(arguments[i])) {
                return arguments[i];
            }
        }
        return arguments[i];
    },
    or: function () {
        // last argument is Handlebars options
        if (arguments.length < 2) {
            return false;
        }
        var i;
        for (i = 0; i < arguments.length - 2; i += 1) {
            if (arguments[i] && !Handlebars.Utils.isEmpty(arguments[i])) {
                return arguments[i];
            }
        }
        return arguments[i];
    },
    not: function (a) { return !a || Handlebars.Utils.isEmpty(a); },
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

window.templates = exports;
