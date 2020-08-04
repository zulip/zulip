"use strict";

module.exports = {
    extends: ["stylelint-config-standard", "stylelint-config-prettier"],
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

        // Disable standard rules we don't comply with yet
        "comment-empty-line-before": null,
        "declaration-empty-line-before": null,
        "length-zero-no-unit": null,

        // Limit language features
        "color-no-hex": true,
        "color-named": "never",
    },
};
