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

// Breakpoints for middle column
const mc = 849; // Middle column as wide as it appears after the `sm` breakpoint

// Breakpoints for showing and hiding compose buttons which do not always fit in
// a single row below the compose box
const cb1 = 1314;
const cb2 = 1072;
const cb3 = 860;
const cb4 = 750;
const cb5 = 504;

export const media_breakpoints = {
    xs_min: xs + "px",
    sm_min: sm + "px",
    md_min: md + "px",
    mc_min: mc + "px",
    lg_min: lg + "px",
    xl_min: xl + "px",
    ml_min: ml + "px",
    mm_min: mm + "px",
    ms_min: ms + "px",
    cb1_min: cb1 + "px",
    cb2_min: cb2 + "px",
    cb3_min: cb3 + "px",
    cb4_min: cb4 + "px",
    cb5_min: cb5 + "px",
    short_navbar_cutoff_height: "600px",
};

export const media_breakpoints_num = {
    xs,
    sm,
    md,
    mc,
    lg,
    xl,
    ml,
    mm,
    ms,
};
