"use strict";

module.exports = {
    extends: ["stylelint-config-standard"],
    rules: {
        // Add some exceptions for recommended rules
        "at-rule-no-unknown": [true, {ignoreAtRules: ["extend"]}],
        "font-family-no-missing-generic-family-keyword": [
            true,
            {ignoreFontFamilies: ["FontAwesome"]},
        ],

        // Disable recommended rules we don't comply with yet
        "media-query-no-invalid": null,
        "no-descending-specificity": null,

        // Disable standard rules we don't comply with yet
        "comment-empty-line-before": null,
        "declaration-empty-line-before": null,
        "keyframes-name-pattern": null,
        "selector-class-pattern": null,
        "selector-id-pattern": null,

        // Limit language features
        "color-no-hex": true,
        "color-named": "never",
        "declaration-property-value-disallowed-list": {
            // thin/medium/thick is under-specified, please use pixels
            "/^(border(-top|-right|-bottom|-left)?|outline)(-width)?$/": [
                /\b(thin|medium|thick)\b/,
            ],
            // no quotation marks around grid-area; use
            // `grid-area: my_area`, not `grid-area: "my_area"`
            "grid-area": [/".*"/],
        },
        "function-disallowed-list": [
            // We use hsl instead of rgb
            "rgb",
        ],

        // Zulip CSS should have no dependencies on external resources
        "function-url-no-scheme-relative": true,
        "function-url-scheme-allowed-list": [
            "data", // Allow data URLs
        ],
    },
};
