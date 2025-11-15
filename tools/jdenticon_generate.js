#!/usr/bin/env node
// tools/jdenticon_generate.js
import * as jdenticon from "jdenticon";

const seed = process.argv[2] || "anon";
const size = Number.parseInt(process.argv[3], 10) || 80;

// Optional: configure per design link in issue
jdenticon.configure({
    lightness: {color: [0.4, 0.8], grayscale: [0.25, 0.9]},
    saturation: {color: 0.7, grayscale: 0.18},
    backColor: "#0000",
});

const svg = jdenticon.toSvg(seed, size);
process.stdout.write(svg);
