"use strict";

module.exports = {
    extends: ["stylelint-config-prettier"],
    rules: {
        // Stylistic rules for CSS.
        "function-whitespace-after": "always",

        "value-keyword-case": "lower",

        "selector-attribute-operator-space-after": "never",
        "selector-attribute-operator-space-before": "never",
        "selector-pseudo-element-colon-notation": "double",
        "selector-type-case": "lower",

        "media-feature-range-operator-space-after": "always",
        "media-feature-range-operator-space-before": "always",

        "comment-whitespace-inside": "always",

        // Limit language features
        "color-no-hex": true,
        "color-named": "never",
    },
};
