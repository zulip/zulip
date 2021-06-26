// Convert an sRGB value in [0, 255] to a linear intensity
// value in [0, 1].
//
// https://en.wikipedia.org/wiki/SRGB#The_reverse_transformation
export function sRGB_to_linear(v: number): number {
    v = v / 255;
    if (v <= 0.04045) {
        return v / 12.92;
    }
    return Math.pow((v + 0.055) / 1.055, 2.4);
}

// Compute luminance (CIE Y stimulus) from linear intensity
// of sRGB / Rec. 709 primaries.
export function rgb_luminance(channel: [number, number, number]): number {
    return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2];
}

// Convert luminance (photometric, CIE Y)
// to lightness (perceptual, CIE L*)
//
// https://en.wikipedia.org/wiki/Lab_color_space#Forward_transformation
export function luminance_to_lightness(luminance: number): number {
    let v;
    if (luminance <= 216 / 24389) {
        v = (841 / 108) * luminance + 4 / 29;
    } else {
        v = Math.pow(luminance, 1 / 3);
    }

    return 116 * v - 16;
}
