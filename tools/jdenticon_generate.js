#!/usr/bin/env node
// tools/jdenticon_generate.js
import * as jdenticon from "jdenticon";

const seed = process.argv[2] || "anon";
const size = parseInt(process.argv[3], 10) || 80;

// Optional: configure per design link in issue
jdenticon.configure({
    lightness: { color: [0.40, 0.80], grayscale: [0.25, 0.90] },
    saturation: { color: 0.70, grayscale: 0.18 },
    backColor: "#0000",
});

const svg = jdenticon.toSvg(seed, size);
process.stdout.write(svg);
