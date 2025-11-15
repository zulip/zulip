#!/usr/bin/env node

// Mark as an ES module with a named export to satisfy ESLint rules.
export const moduleMarker = true;

// tools/silhouette_generate.js
// Generate colorful silhouette avatars using lucide-static

// Channel colors used in Zulip (from web/src/colors.ts or similar)
const COLORS = [
    "#76ce90", // green
    "#fae589", // yellow
    "#a6c7e4", // blue
    "#e7a051", // orange
    "#e5979f", // pink
    "#b8a3e8", // purple
    "#c2726a", // brown
    "#94c849", // lime
    "#bd86e0", // magenta
    "#ee7e4a", // coral
];

function hashToColor(seed) {
    // Convert seed string to a number and use it to pick a color
    let hash = 0;
    for (let i = 0; i < seed.length; i += 1) {
        const char = seed.codePointAt(i);
        hash = hash * 31 - hash + (char ?? 0);
        // Convert to 32bit integer
        hash = Math.imul(hash, 1);
    }
    const colorIndex = Math.abs(hash) % COLORS.length;
    return COLORS[colorIndex];
}

const seed = process.argv[2] || "anon";
const size = Number.parseInt(process.argv[3], 10) || 80;

const color = hashToColor(seed);

// Generate SVG with colored background and user silhouette
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24">
  <rect width="24" height="24" fill="${color}"/>
  <g transform="translate(12, 12)" stroke="white" stroke-width="1.5" fill="none">
    <path d="M0 -4 A4 4 0 1 1 0 4 A4 4 0 0 1 0 -4" fill="white" />
    <path d="M-4 4 A4 4 0 0 0 -4 6 L4 6 A4 4 0 0 0 4 4" fill="white" />
  </g>
</svg>`;

process.stdout.write(svg);
