"use strict";

module.exports = {
    extends: ["stylelint-config-standard", "stylelint-config-prettier"],
    rules: {
        // Add some exceptions for recommended rules
        "at-rule-no-unknown": [true, {ignoreAtRules: ["extend"]}],

        // Disable recommended rules we don't comply with yet
        "font-family-no-missing-generic-family-keyword": null,
        "no-descending-specificity": null,

        // Disable standard rules we don't comply with yet
        "comment-empty-line-before": null,
        "declaration-empty-line-before": null,

        // Additional stylistic rules
        "font-family-name-quotes": "always-where-recommended",
        "function-url-quotes": "never",

        // Limit language features
        "color-no-hex": true,
        "color-named": "never",
        "declaration-property-value-disallowed-list": {
            // thin/medium/thick is under-specified, please use pixels
            "/^(border(-top|-right|-bottom|-left)?|outline)(-width)?$/": [
                /\b(thin|medium|thick)\b/,
            ],
        },
        "function-disallowed-list": [
            // We use hsl(a) instead of rgb(a)
            "rgb",
            "rgba",
        ],

        // Zulip CSS should have no dependencies on external resources
        "function-url-no-scheme-relative": true,
        "function-url-scheme-allowed-list": [],

        // We use autoprefixer to generate vendor prefixes
        "at-rule-no-vendor-prefix": true,
        "media-feature-name-no-vendor-prefix": true,
        "property-no-vendor-prefix": true,
        "selector-no-vendor-prefix": true,
        "value-no-vendor-prefix": true,
    },
};
