var colorspace = (function () {

var exports = {};

// Convert an sRGB value in [0, 255] to a linear intensity
// value in [0, 1].
//
// http://en.wikipedia.org/wiki/SRGB#The_reverse_transformation
exports.sRGB_to_linear = function (v) {
    v = v / 255.0;
    if (v <= 0.04045) {
        return v / 12.92;
    }
    return Math.pow((v + 0.055) / 1.055, 2.4);
};

// Compute luminance (CIE Y stimulus) from linear intensity
// of sRGB / Rec. 709 primaries.
exports.rgb_luminance = function (channel) {
    return 0.2126*channel[0] + 0.7152*channel[1] + 0.0722*channel[2];
};

// Convert luminance (photometric, CIE Y)
// to lightness (perceptual, CIE L*)
//
// http://en.wikipedia.org/wiki/Lab_color_space#Forward_transformation
exports.luminance_to_lightness = function (luminance) {
    var v;
    if (luminance <= (216 / 24389)) {
        v = (841 / 108)*luminance + (4 / 29);
    } else {
        v = Math.pow(luminance, 1/3);
    }

    return 116*v - 16;
};

exports.getDecimalColor = function (hexcolor) {
    return {r: parseInt(hexcolor.substr(1,2), 16),
            g: parseInt(hexcolor.substr(3,2), 16),
            b: parseInt(hexcolor.substr(5,2), 16)};
};

exports.getLighterColor = function (rgb, lightness) {
    return {r: (lightness * 255 + (1 - lightness) * rgb.r).toFixed(),
            g: (lightness * 255 + (1 - lightness) * rgb.g).toFixed(),
            b: (lightness * 255 + (1 - lightness) * rgb.b).toFixed()};
};

exports.getHexColor = function (rgb) {
    return "#" + parseInt(rgb.r, 10).toString(16) +
                 parseInt(rgb.g, 10).toString(16) +
                 parseInt(rgb.b, 10).toString(16);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = colorspace;
}
