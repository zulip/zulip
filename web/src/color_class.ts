import _ from "lodash";

import * as colorspace from "./colorspace";

export function get_threshold(): number {
    // sRGB color component for dark label text.
    // 0x33 to match the color #333333 set by Bootstrap.
    const label_color = 0x33;
    const lightness = colorspace.luminance_to_lightness(colorspace.sRGB_to_linear(label_color));

    // Compute midpoint lightness between that and white (100).
    return (lightness + 100) / 2;
}

const lightness_threshold = get_threshold();

// From a background color (in format "#fff" or "#ffffff")
// pick a CSS class (or empty string) to determine the
// text label color etc.
//
// It would be better to work with an actual data structure
// rather than a hex string, but we have to deal with values
// already saved on the server, etc.
//
// This gets called on every message, so cache the results.
export const get_css_class = _.memoize((color: string) => {
    let match;
    let i;
    const channel: [number, number, number] = [0, 0, 0];
    let mult = 1;

    match = /^#([\dA-Fa-f]{2})([\dA-Fa-f]{2})([\dA-Fa-f]{2})$/.exec(color);
    if (!match) {
        // 3-digit shorthand; Spectrum gives this e.g. for pure black.
        // Multiply each digit by 16+1.
        mult = 17;

        match = /^#([\dA-Fa-f])([\dA-Fa-f])([\dA-Fa-f])$/.exec(color);
        if (!match) {
            // Can't understand color.
            return "";
        }
    }

    // CSS colors are specified in the sRGB color space.
    // Convert to linear intensity values.
    for (i = 0; i < 3; i += 1) {
        channel[i] = colorspace.sRGB_to_linear(mult * Number.parseInt(match[i + 1], 16));
    }

    // Compute perceived lightness as CIE L*.
    const lightness = colorspace.luminance_to_lightness(colorspace.rgb_luminance(channel));

    // Determine if we're past the midpoint between the
    // dark and light label lightness.
    return lightness < lightness_threshold ? "dark_background" : "";
});
