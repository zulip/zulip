"use strict";

const {media_breakpoints} = require("./static/js/css_variables");

module.exports = {
    plugins: [
        require("postcss-nested"),
        require("postcss-extend-rule"),
        require("postcss-simple-vars")({variables: media_breakpoints}),
        require("postcss-calc"),
        require("postcss-media-minmax"),
        require("autoprefixer"),
    ],
};
