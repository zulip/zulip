"use strict";

module.exports = {
    extends: ["stylelint-config-standard", "stylelint-config-prettier"],
    rules: {
        // Add some exceptions for recommended rules
        "at-rule-no-unknown": [true, {ignoreAtRules: ["extend"]}],
        "font-family-no-missing-generic-family-keyword": [
            true,
            {ignoreFontFamilies: ["FontAwesome"]},
        ],

        // Disable recommended rules we don't comply with yet
        "no-descending-specificity": null,

        // Disable standard rules we don't comply with yet
        "comment-empty-line-before": null,
        "declaration-empty-line-before": null,
        "keyframes-name-pattern": null,
        "selector-class-pattern": null,
        "selector-id-pattern": null,

        // Compatibility with older browsers
        "alpha-value-notation": "number",
        "color-function-notation": "legacy",
        "hue-degree-notation": "number",

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
        "function-url-scheme-allowed-list": [
            "data", // Allow data URIs
        ],
    },
};
