import type {Colord} from "colord";
import {colord, extend} from "colord";
import lchPlugin from "colord/plugins/lch";
import mixPlugin from "colord/plugins/mix";

import * as settings_data from "./settings_data.ts";
import * as stream_data from "./stream_data.ts";

extend([lchPlugin, mixPlugin]);

export function update_stream_recipient_color($stream_header: JQuery, color?: string): void {
    if ($stream_header.length > 0) {
        const stream_id = Number.parseInt($stream_header.attr("data-stream-id")!, 10);
        if (!stream_id) {
            return;
        }
        const stream_color = color ?? stream_data.get_color(stream_id);
        const recipient_bar_color = get_recipient_bar_color(stream_color);

        const $stream_privacy_icon = $stream_header.find(".stream-privacy");
        if ($stream_privacy_icon.length > 0) {
            $stream_privacy_icon.css("color", get_stream_privacy_icon_color(stream_color));
        }

        $stream_header
            .find(".message-header-contents")
            .css("background-color", recipient_bar_color);
    }
}

export function get_corrected_color(hex_color: string): Colord {
    // LCH stands for Lightness, Chroma, and Hue.
    // This function restricts Lightness of a color to be between 20 to 75.
    const color = colord(hex_color).toLch();
    const min_color_l = 20;
    const max_color_l = 75;
    if (color.l < min_color_l) {
        color.l = min_color_l;
    } else if (color.l > max_color_l) {
        color.l = max_color_l;
    }
    return colord(color);
}

export function get_stream_privacy_icon_color(hex_color: string): string {
    const corrected_color = get_corrected_color(hex_color);
    if (settings_data.using_dark_theme()) {
        return corrected_color.toHex();
    }
    return corrected_color.darken(0.12).toHex();
}

export function get_recipient_bar_color(color: string): string {
    // Mixes 50% of color to 40% of white (light theme) / black (dark theme).
    const using_dark_theme = settings_data.using_dark_theme();
    color = get_corrected_color(color).toHex();
    return colord(using_dark_theme ? "#000000" : "#f9f9f9")
        .mix(color, using_dark_theme ? 0.38 : 0.22)
        .toHex();
}

export const stream_color_palette = [
    ["#a47462", "#c2726a", "#e4523d", "#e7664d", "#ee7e4a", "#f4ae55"],
    ["#76ce90", "#53a063", "#94c849", "#bfd56f", "#fae589", "#f5ce6e"],
    ["#a6dcbf", "#addfe5", "#a6c7e5", "#4f8de4", "#95a5fd", "#b0a5fd"],
    ["#c2c2c2", "#c8bebf", "#c6a8ad", "#e79ab5", "#bd86e5", "#9987e1"],
];
