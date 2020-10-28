"use strict";


// Media query breakpoints according to Bootstrap 3.4.1
const xs = 480
const sm = 768
const md = 992
const lg = 1200
const xl = 1400

module.exports = {
    plugins: {
        // Warning: despite appearances, order is significant
        "postcss-nested": {},
        "postcss-extend-rule": {},
        "postcss-simple-vars": {
            variables: {
                "xs-min": xs + "px",
                "sm-min": sm + "px",
                "md-min": md + "px",
                "lg-min": lg + "px",
                "xl-min": xl + "px",

                "xs-max": xs - 1 + "px",
                "sm-max": sm - 1 + "px",
                "md-max": md - 1 + "px",
                "lg-max": lg - 1 + "px",
                "xl-max": xl - 1 + "px",
            }
        },
        "postcss-calc": {},
        autoprefixer: {},
    },
};
