import {colord, extend} from "colord";
import lchPlugin from "colord/plugins/lch";
import mixPlugin from "colord/plugins/mix";
import $ from "jquery";

import {$t} from "./i18n";
import * as settings_data from "./settings_data";
import * as stream_data from "./stream_data";
import * as stream_settings_ui from "./stream_settings_ui";

extend([lchPlugin, mixPlugin]);

export function update_stream_recipient_color($stream_header) {
    if ($stream_header.length) {
        const stream_id = Number.parseInt($($stream_header).attr("data-stream-id"), 10);
        if (!stream_id) {
            return;
        }
        const stream_color = stream_data.get_color(stream_id);
        const recipient_bar_color = get_recipient_bar_color(stream_color);
        $stream_header
            .find(".message-header-contents")
            .css("background-color", recipient_bar_color);
    }
}

export function get_stream_privacy_icon_color(color) {
    // LCH stands for Lightness, Chroma, and Hue.
    // This function restricts Lightness of a color to be between 20 to 75.
    color = colord(color).toLch();
    const min_color_l = 20;
    const max_color_l = 75;
    if (color.l < min_color_l) {
        color.l = min_color_l;
    } else if (color.l > max_color_l) {
        color.l = max_color_l;
    }
    return colord(color).toHex();
}

export function get_recipient_bar_color(color) {
    // Mixes 50% of color to 40% of white (light theme) / black (dark theme).
    const using_dark_theme = settings_data.using_dark_theme();
    color = get_stream_privacy_icon_color(color);
    return colord(using_dark_theme ? "#000000" : "#f9f9f9")
        .mix(color, using_dark_theme ? 0.38 : 0.22)
        .toHex();
}

const stream_color_palette = [
    ["a47462", "c2726a", "e4523d", "e7664d", "ee7e4a", "f4ae55"],
    ["76ce90", "53a063", "94c849", "bfd56f", "fae589", "f5ce6e"],
    ["a6dcbf", "addfe5", "a6c7e5", "4f8de4", "95a5fd", "b0a5fd"],
    ["c2c2c2", "c8bebf", "c6a8ad", "e79ab5", "bd86e5", "9987e1"],
];

const subscriptions_table_colorpicker_options = {
    clickoutFiresChange: true,
    showPalette: true,
    showInput: true,
    palette: stream_color_palette,
};

export function set_colorpicker_color(colorpicker, color) {
    colorpicker.spectrum({
        ...subscriptions_table_colorpicker_options,
        color,
        container: "#subscription_overlay .subscription_settings.show",
    });
}

export const sidebar_popover_colorpicker_options_full = {
    clickoutFiresChange: false,
    showPalette: true,
    showInput: true,
    flat: true,
    cancelText: "",
    chooseText: $t({defaultMessage: "Confirm"}),
    palette: stream_color_palette,
    change: picker_do_change_color,
};

function picker_do_change_color(color) {
    $(".colorpicker").spectrum("destroy");
    $(".colorpicker").spectrum(sidebar_popover_colorpicker_options_full);
    const stream_id = Number.parseInt($(this).attr("stream_id"), 10);
    const hex_color = color.toHexString();
    stream_settings_ui.set_color(stream_id, hex_color);
}
subscriptions_table_colorpicker_options.change = picker_do_change_color;

export const sidebar_popover_colorpicker_options = {
    clickoutFiresChange: true,
    showPaletteOnly: true,
    showPalette: true,
    showInput: true,
    flat: true,
    palette: stream_color_palette,
    change: picker_do_change_color,
};
