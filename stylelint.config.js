"use strict";

module.exports = {
    extends: ["stylelint-config-recommended", "stylelint-config-prettier"],
    rules: {
        // Add some exceptions for recommended rules
        "at-rule-no-unknown": [true, {ignoreAtRules: ["extend"]}],
        "property-no-unknown": [true, {ignoreProperties: [/^mso-/, "user-drag"]}],

        // Disable recommended rules we don't comply with yet
        "declaration-block-no-duplicate-properties": null,
        "declaration-block-no-shorthand-property-overrides": null,
        "font-family-no-missing-generic-family-keyword": null,
        "no-descending-specificity": null,
        "no-duplicate-selectors": null,

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
