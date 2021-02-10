// Convert an sRGB value in [0, 255] to a linear intensity
// value in [0, 1].
//
// https://en.wikipedia.org/wiki/SRGB#The_reverse_transformation
export function sRGB_to_linear(v) {
    v = v / 255;
    if (v <= 0.04045) {
        return v / 12.92;
    }
    return Math.pow((v + 0.055) / 1.055, 2.4);
}

// Compute luminance (CIE Y stimulus) from linear intensity
// of sRGB / Rec. 709 primaries.
export function rgb_luminance(channel) {
    return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2];
}

// Convert luminance (photometric, CIE Y)
// to lightness (perceptual, CIE L*)
//
// https://en.wikipedia.org/wiki/Lab_color_space#Forward_transformation
export function luminance_to_lightness(luminance) {
    let v;
    if (luminance <= 216 / 24389) {
        v = (841 / 108) * luminance + 4 / 29;
    } else {
        v = Math.pow(luminance, 1 / 3);
    }

    return 116 * v - 16;
}

export function getDecimalColor(hexcolor) {
    return {
        r: Number.parseInt(hexcolor.slice(1, 3), 16),
        g: Number.parseInt(hexcolor.slice(3, 5), 16),
        b: Number.parseInt(hexcolor.slice(5, 7), 16),
    };
}

export function getLighterColor(rgb, lightness) {
    return {
        r: Math.round(lightness * 255 + (1 - lightness) * rgb.r),
        g: Math.round(lightness * 255 + (1 - lightness) * rgb.g),
        b: Math.round(lightness * 255 + (1 - lightness) * rgb.b),
    };
}

export function getHexColor(rgb) {
    return (
        "#" +
        Number.parseInt(rgb.r, 10).toString(16) +
        Number.parseInt(rgb.g, 10).toString(16) +
        Number.parseInt(rgb.b, 10).toString(16)
    );
}
