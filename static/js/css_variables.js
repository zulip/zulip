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
        xs_min: xs + "px",
        sm_min: sm + "px",
        md_min: md + "px",
        lg_min: lg + "px",
        xl_min: xl + "px",
        ml_min: ml + "px",
        mm_min: mm + "px",
        ms_min: ms + "px",
    },
};
