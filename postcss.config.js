"use strict";

const {media_breakpoints} = require("./static/js/css_variables.js");
const vertical_px_to_rem = require("./postcss/vertical_px_to_rem");

module.exports = {
    plugins: [
        // Warning: despite appearances, order is significant
        [vertical_px_to_rem, {}],
        ["postcss-nested", {}],
        ["postcss-extend-rule", {}],
        ["postcss-simple-vars", {
            variables: media_breakpoints,
        }],
        ["postcss-calc", {}],
        ["postcss-media-minmax", {}],
        ["autoprefixer", {}],
    ],
};
