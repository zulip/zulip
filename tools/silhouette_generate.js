#!/usr/bin/env node

// Mark as an ES module with a named export to satisfy ESLint rules.
export const moduleMarker = true;

// tools/silhouette_generate.js
// Generate colorful silhouette avatars using Lucide user icon
// https://lucide.dev/icons/user

// Channel colors from STREAM_ASSIGNMENT_COLORS in zerver/lib/stream_color.py
// These must match exactly with the Python implementation
const COLORS = [
    "#76ce90",
    "#fae589",
    "#a6c7e5",
    "#e79ab5",
    "#bfd56f",
    "#f4ae55",
    "#b0a5fd",
    "#addfe5",
    "#f5ce6e",
    "#c2726a",
    "#94c849",
    "#bd86e5",
    "#ee7e4a",
    "#a6dcbf",
    "#95a5fd",
    "#53a063",
    "#9987e1",
    "#e4523d",
    "#c2c2c2",
    "#4f8de4",
    "#c6a8ad",
    "#e7cc4d",
    "#c8bebf",
    "#a47462",
];

function getColorFromSeed(seed) {
    // Convert seed string to a number and use it to pick a color
    // This matches the Python implementation: user_id % len(STREAM_ASSIGNMENT_COLORS)
    const seedNum = Number.parseInt(seed, 10);
    if (!Number.isNaN(seedNum)) {
        return COLORS[seedNum % COLORS.length];
    }

    // Fallback for non-numeric seeds: use hash
    let hash = 0;
    for (let i = 0; i < seed.length; i += 1) {
        const char = seed.codePointAt(i);
        hash = hash * 31 - hash + (char ?? 0);
        hash = Math.imul(hash, 1);
    }
    const colorIndex = Math.abs(hash) % COLORS.length;
    return COLORS[colorIndex];
}

const seed = process.argv[2] || "anon";
const size = Number.parseInt(process.argv[3], 10) || 80;

const color = getColorFromSeed(seed);

// Lucide user icon SVG from https://lucide.dev/icons/user
// The user icon consists of:
// 1. A circle for the head: cx="12" cy="7" r="4"
// 2. A path for the body/shoulders: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"

// Generate SVG with colored background and Lucide user icon
// Using white fill for the icon on the colored background
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24">
  <rect width="24" height="24" fill="${color}" rx="4"/>
  <circle cx="12" cy="7" r="4" fill="white"/>
  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" fill="white"/>
</svg>`;

process.stdout.write(svg);
