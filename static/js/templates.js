"use strict";

const Handlebars = require("handlebars/runtime");

const util = require("./util");

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

Handlebars.registerHelper("plural", (condition, one, other) => (condition === 1 ? one : other));

Handlebars.registerHelper({
    eq(a, b) {
        return a === b;
    },
    and(...args) {
        args.pop(); // Handlebars options
        if (args.length === 0) {
            return true;
        }
        const last = args.pop();
        for (const arg of args) {
            if (!arg || Handlebars.Utils.isEmpty(arg)) {
                return arg;
            }
        }
        return last;
    },
    or(...args) {
        args.pop(); // Handlebars options
        if (args.length === 0) {
            return false;
        }
        const last = args.pop();
        for (const arg of args) {
            if (arg && !Handlebars.Utils.isEmpty(arg)) {
                return arg;
            }
        }
        return last;
    },
    not(a) {
        return !a || Handlebars.Utils.isEmpty(a);
    },
});

// Note that this i18n caching strategy does not allow us to support
// live-updating the UI language without reloading the Zulip browser
// window.  That constraint would be very hard to change in any case,
// though, because of how Zulip renders some strings using the backend
// Jinja2 templating engine, so we don't consider this important.
const t_cache = new Map();

Handlebars.registerHelper("t", (i18n_key) => {
    // Marks a string for translation.
    // Example usage:
    //     {{t "some English text"}}

    const cache_result = t_cache.get(i18n_key);
    if (cache_result !== undefined) {
        return cache_result;
    }
    const result = i18n.t(i18n_key);
    const safe_result = new Handlebars.SafeString(result);
    t_cache.set(i18n_key, safe_result);
    return safe_result;
});

Handlebars.registerHelper("tr", (context, options) => {
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
    const result = i18n.t(
        options
            .fn(context)
            .trim()
            .split("\n")
            .map((s) => s.trim())
            .join(" "),
        context,
    );
    return new Handlebars.SafeString(result);
});

Handlebars.registerHelper(
    "rendered_markdown",
    (content) => new Handlebars.SafeString(util.clean_user_content_links(content)),
);

Handlebars.registerHelper("numberFormat", (number) => number.toLocaleString());

window.templates = exports;
