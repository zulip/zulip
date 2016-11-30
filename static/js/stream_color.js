var stream_color = (function () {

var exports = {};

exports.default_color = "#c2c2c2";
// Auto-assigned colors should be from the default palette so it's easy to undo
// changes, so if that pallete changes, change these colors.
var stream_assignment_colors = ["#76ce90", "#fae589", "#a6c7e5", "#e79ab5",
                                "#bfd56f", "#f4ae55", "#b0a5fd", "#addfe5",
                                "#f5ce6e", "#c2726a", "#94c849", "#bd86e5",
                                "#ee7e4a", "#a6dcbf", "#95a5fd", "#53a063",
                                "#9987e1", "#e4523d", "#c2c2c2", "#4f8de4",
                                "#c6a8ad", "#e7cc4d", "#c8bebf", "#a47462"];

// Classes which could be returned by get_color_class.
exports.color_classes = 'dark_background';

exports.pick_color = function (used_colors) {
    var colors = _.shuffle(stream_assignment_colors);
    var used_color_hash = {};

    _.each(used_colors, function (color) {
        used_color_hash[color] = true;
    });

    var color = _.find(colors, function (color) {
        return !_.has(used_color_hash, color);
    });

    if (color) {
        return color;
    }

    // All available colors were used.
    return colors[0];
};

function update_table_stream_color(table, stream_name, color) {
    // This is ugly, but temporary, as the new design will make it
    // so that we only have color in the headers.

    var payload = exports.lighter_stream_colors(color);

    var stream_labels = $("#floating_recipient_bar")
        .add(table).find(".stream_label .display-recipient-block");

    _.each(stream_labels, function (label) {
        var $label = $(label);

        if ($.trim($label.text()) === stream_name) {
            $label.closest(".message-header-contents").css("background", payload.light);
            $label.closest(".message-header-contents")
                .find(".display-recipient-icon")
                .css("color", payload.medium);
        }
    });
}

function update_stream_sidebar_swatch_color(id, color) {
    $("#stream_sidebar_swatch_" + id).css('background-color', color);
    $("#stream_sidebar_privacy_swatch_" + id).css('color', color);
}

function update_historical_message_color(stream_name, color) {
    update_table_stream_color($(".focused_table"), stream_name, color);
    if ($(".focused_table").attr("id") !== "#zhome") {
        update_table_stream_color($("#zhome"), stream_name, color);
    }
}

var stream_color_palette = [
    ['a47462', 'c2726a', 'e4523d', 'e7664d', 'ee7e4a', 'f4ae55'],
    ['76ce90', '53a063', '94c849', 'bfd56f', 'fae589', 'f5ce6e'],
    ['a6dcbf', 'addfe5', 'a6c7e5', '4f8de4', '95a5fd', 'b0a5fd'],
    ['c2c2c2', 'c8bebf', 'c6a8ad', 'e79ab5', 'bd86e5', '9987e1'],
];

var subscriptions_table_colorpicker_options = {
    clickoutFiresChange: true,
    showPalette: true,
    showInput: true,
    palette: stream_color_palette,
};

exports.set_colorpicker_color = function (colorpicker, color) {
    colorpicker.spectrum(_.extend(subscriptions_table_colorpicker_options,
                         {color: color, container: "#subscription_overlay .subscription_settings.show"}));
};

exports.update_stream_color = function (sub, color, opts) {
    opts = _.defaults({}, opts, {update_historical: false});
    sub.color = color;
    var id = parseInt(sub.stream_id, 10);
    // The swatch in the subscription row header.
    $(".stream-row[data-stream-id='" + id + "'] .icon").css('background-color', color);
    // The swatch in the color picker.
    exports.set_colorpicker_color($("#subscription_overlay .subscription_settings[data-stream-id='" + id + "'] .colorpicker"), color);
    $("#subscription_overlay .subscription_settings[data-stream-id='" + id + "'] .large-icon").css("color", color);

    if (opts.update_historical) {
        update_historical_message_color(sub.name, color);
    }
    update_stream_sidebar_swatch_color(id, color);
    tab_bar.colorize_tab_bar();
};

function picker_do_change_color(color) {
    var stream_id = $(this).attr('stream_id');
    var hex_color = color.toHexString();
    subs.set_color(stream_id, hex_color);
}
subscriptions_table_colorpicker_options.change = picker_do_change_color;

exports.sidebar_popover_colorpicker_options = {
    clickoutFiresChange: true,
    showPaletteOnly: true,
    showPalette: true,
    showInput: true,
    flat: true,
    palette: stream_color_palette,
    change: picker_do_change_color,
};

exports.sidebar_popover_colorpicker_options_full = {
    clickoutFiresChange: true,
    showPalette: true,
    showInput: true,
    flat: true,
    cancelText: "",
    chooseText: "choose",
    palette: stream_color_palette,
    change: picker_do_change_color,
};

var lightness_threshold;
$(function () {
    // sRGB color component for dark label text.
    // 0x33 to match the color #333333 set by Bootstrap.
    var label_color = 0x33;
    var lightness = colorspace.luminance_to_lightness(
        colorspace.sRGB_to_linear(label_color));

    // Compute midpoint lightness between that and white (100).
    lightness_threshold = (lightness + 100) / 2;
});

// From a background color (in format "#fff" or "#ffffff")
// pick a CSS class (or empty string) to determine the
// text label color etc.
//
// It would be better to work with an actual data structure
// rather than a hex string, but we have to deal with values
// already saved on the server, etc.
//
// This gets called on every message, so cache the results.
exports.get_color_class = _.memoize(function (color) {
    var match;
    var i;
    var lightness;
    var channel = [0, 0, 0];
    var mult = 1;

    match = /^#([\da-fA-F]{2})([\da-fA-F]{2})([\da-fA-F]{2})$/.exec(color);
    if (!match) {
        // 3-digit shorthand; Spectrum gives this e.g. for pure black.
        // Multiply each digit by 16+1.
        mult = 17;

        match = /^#([\da-fA-F])([\da-fA-F])([\da-fA-F])$/.exec(color);
        if (!match) {
            // Can't understand color.
            return '';
        }
    }

    // CSS colors are specified in the sRGB color space.
    // Convert to linear intensity values.
    for (i=0; i<3; i += 1) {
        channel[i] = colorspace.sRGB_to_linear(mult * parseInt(match[i+1], 16));
    }

    // Compute perceived lightness as CIE L*.
    lightness = colorspace.luminance_to_lightness(
        colorspace.rgb_luminance(channel));

    // Determine if we're past the midpoint between the
    // dark and light label lightness.
    return (lightness < lightness_threshold) ? 'dark_background' : '';
});

exports.rgb_to_hsl = function (r, g, b) {
    r /= 255;
    g /= 255;
    b /= 255;
    var max = Math.max(r, g, b);
    var min = Math.min(r, g, b);
    var h;
    var s;
    var l = (max + min) / 2;

    if (max === min) {
        h = s = 0;
    } else {
        var d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);

        switch (max) {
            case r: h = (g - b) / d + (g < b ? 6 : 0); break;
            case g: h = (b - r) / d + 2; break;
            case b: h = (r - g) / d + 4; break;
        }

        h /= 6;
    }

    return [(h*3.6*100+0.5) || 0, ((s*100+0.5) || 0) + '%', ((l*100+0.5) || 0) + '%'];
};

exports.hex_to_hsl = function (hex) {
    if (/^#/.test(hex)) {
        hex = hex.replace("#", "");
    }

    var rgb = hex.match(/.{2}/g).map(function (o) {
        return parseInt(o, 16);
    });

    return exports.rgb_to_hsl.apply(null, rgb);
};

exports.lighter_stream_colors = function (hex) {
    var hsl = exports.hex_to_hsl(hex);

    var light = hsl.slice(0, 2).concat("90%");
    var medium = hsl.slice(0, 2).concat("50%");

    return {
        light: "hsl(" + light.join(",") + ")",
        medium: "hsl(" + medium + ")",
    };
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = stream_color;
}
