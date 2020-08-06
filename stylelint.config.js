"use strict";

module.exports = {
    extends: ["stylelint-config-standard", "stylelint-config-prettier"],
    rules: {
        // Add some exceptions for recommended rules
        "at-rule-no-unknown": [true, {ignoreAtRules: ["extend"]}],
        "property-no-unknown": [true, {ignoreProperties: [/^mso-/]}],

        // Disable recommended rules we don't comply with yet
        "font-family-no-missing-generic-family-keyword": null,
        "no-descending-specificity": null,
        "no-duplicate-selectors": null,

        // Disable standard rules we don't comply with yet
        "comment-empty-line-before": null,
        "declaration-empty-line-before": null,
        "length-zero-no-unit": null,

        // Additional stylistic rules
        "font-family-name-quotes": "always-where-recommended",
        "function-url-quotes": "never",

        // Limit language features
        "color-no-hex": true,
        "color-named": "never",
        "declaration-property-value-blacklist": {
            // thin/medium/thick is under-specified, please use pixels
            "/^(border(-top|-right|-bottom|-left)?|outline)(-width)?$/": [
                /\b(thin|medium|thick)\b/,
            ],
        },
        "function-blacklist": [
            // We use hsl(a) instead of rgb(a)
            "rgb",
            "rgba",
        ],

        // Zulip CSS should have no dependencies on external resources
        "function-url-no-scheme-relative": true,
        "function-url-scheme-whitelist": [],
    },
};
