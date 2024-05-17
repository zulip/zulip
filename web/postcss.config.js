"use strict";

const path = require("path");

const {media_breakpoints} = require("./src/css_variables");

const config = ({file}) => ({
    plugins: [
        (file.basename ?? path.basename(file)) === "dark_theme.css" &&
            // Add postcss-import plugin with postcss-prefixwrap to handle
            // the flatpickr dark theme. We do this because flatpickr themes
            // are not scoped. See https://github.com/flatpickr/flatpickr/issues/2168.
            require("postcss-import")({
                plugins: [require("postcss-prefixwrap")("%dark-theme")],
            }),
        require("postcss-extend-rule"),
        require("postcss-simple-vars")({variables: media_breakpoints}),
        require("postcss-preset-env")({
            features: {
                "nesting-rules": true,
            },
        }),
    ],
});
module.exports = config;
