"use strict";

// Media query breakpoints according to Bootstrap 4.5
const xs = 0;
const sm = 576;
const md = 768;
const lg = 992;
const xl = 1200;

// Breakpoints for mobile devices used by Google Chrome as of Version 86
const ml = 425; // Mobile large
const mm = 375; // Mobile medium
const ms = 320; // Mobile small

module.exports = {
    media_breakpoints: {
        "xs-min": xs + "px",
        "sm-min": sm + "px",
        "md-min": md + "px",
        "lg-min": lg + "px",
        "xl-min": xl + "px",
        "ml-min": ml + "px",
        "mm-min": mm + "px",
        "ms-min": ms + "px",

        "xs-max": xs - 1 + "px",
        "sm-max": sm - 1 + "px",
        "md-max": md - 1 + "px",
        "lg-max": lg - 1 + "px",
        "xl-max": xl - 1 + "px",
        "ml-max": ml - 1 + "px",
        "mm-max": mm - 1 + "px",
        "ms-max": ms - 1 + "px",
    },
};
