export default {
    extends: ["../../../stylelint.config"],
    rules: {
        // Add some exceptions for recommended rules
        "property-no-unknown": [true, {ignoreProperties: [/^mso-/]}],

        // We don't run autoprefixer on email CSS
        "at-rule-no-vendor-prefix": null,
        "media-feature-name-no-vendor-prefix": null,
        "property-no-vendor-prefix": null,
        "selector-no-vendor-prefix": null,
        "value-no-vendor-prefix": null,
    },
};
