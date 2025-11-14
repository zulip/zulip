#!/usr/bin/env node
// tools/silhouette_generate.js
// Generate colorful silhouette avatars using lucide-static

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Channel colors used in Zulip (from web/src/colors.ts or similar)
const COLORS = [
    "#76ce90",  // green
    "#fae589",  // yellow
    "#a6c7e4",  // blue
    "#e7a051",  // orange
    "#e5979f",  // pink
    "#b8a3e8",  // purple
    "#c2726a",  // brown
    "#94c849",  // lime
    "#bd86e0",  // magenta
    "#ee7e4a",  // coral
];

// Simple user icon SVG
const USER_ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
  <circle cx="12" cy="7" r="4"></circle>
</svg>`;

function hashToColor(seed) {
    // Convert seed string to a number and use it to pick a color
    let hash = 0;
    for (let i = 0; i < seed.length; i++) {
        const char = seed.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
    }
    const colorIndex = Math.abs(hash) % COLORS.length;
    return COLORS[colorIndex];
}

const seed = process.argv[2] || "anon";
const size = parseInt(process.argv[3], 10) || 80;

const color = hashToColor(seed);

// Generate SVG with colored background and user silhouette
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24">
  <rect width="24" height="24" fill="${color}"/>
  <g transform="translate(12, 12)" stroke="white" stroke-width="1.5" fill="none">
    <path d="M0 -4 A4 4 0 1 1 0 4 A4 4 0 0 1 0 -4" fill="white"/>
    <path d="M-4 4 A4 4 0 0 0 -4 6 L4 6 A4 4 0 0 0 4 4" fill="white"/>
  </g>
</svg>`;

process.stdout.write(svg);
