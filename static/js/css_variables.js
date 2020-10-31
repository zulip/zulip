"use strict";

// Media query breakpoints according to Bootstrap 4.5
const xs = 0;
const sm = 576;
const md = 768;
const lg = 992;
const xl = 1200;

module.exports = {
    media_breakpoints: {
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
    },
};
