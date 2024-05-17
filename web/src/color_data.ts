import _ from "lodash";

export let unused_colors: string[];

// These colors are used now for streams.
const stream_colors = [
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

// Shuffle our colors on page load to prevent
// bias toward "early" colors.
export const colors = _.shuffle(stream_colors);

export function reset(): void {
    unused_colors = [...colors];
}

reset();

export function claim_color(color: string): void {
    const i = unused_colors.indexOf(color);

    if (i < 0) {
        return;
    }

    unused_colors.splice(i, 1);

    if (unused_colors.length === 0) {
        reset();
    }
}

export function claim_colors(subs: {color: string}[]): void {
    const colors = new Set(subs.map((sub) => sub.color));
    for (const color of colors) {
        claim_color(color);
    }
}

export function pick_color(): string {
    const color = unused_colors[0];

    claim_color(color);

    return color;
}
