import {colord, extend} from "colord";
import lchPlugin from "colord/plugins/lch";
import $ from "jquery";

import * as color_class from "./color_class";
import {$t} from "./i18n";
import * as message_view_header from "./message_view_header";
import * as settings_data from "./settings_data";
import * as stream_settings_ui from "./stream_settings_ui";

extend([lchPlugin]);

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
    // Mixes 20% of color to 80% of white (light theme) / black (dark theme).
    const using_dark_theme = settings_data.using_dark_theme();
    color = get_stream_privacy_icon_color(color);
    const {r, g, b} = colord(color).toRgb();
    return colord({
        r: 0.8 * (using_dark_theme ? 0 : 255) + 0.2 * r,
        g: 0.8 * (using_dark_theme ? 0 : 255) + 0.2 * g,
        b: 0.8 * (using_dark_theme ? 0 : 255) + 0.2 * b,
    }).toHex();
}

function update_table_stream_color(table, stream_name, color) {
    // This is ugly, but temporary, as the new design will make it
    // so that we only have color in the headers.
    const style = color;
    const recipient_bar_color = get_recipient_bar_color(color);

    const $stream_labels = table.find(".stream_label");

    for (const label of $stream_labels) {
        const $label = $(label);
        if ($label.text().trim() === stream_name) {
            const $messages = $label.closest(".recipient_row").children(".message_row");
            $messages
                .children(".messagebox")
                .css(
                    "box-shadow",
                    "inset 2px 0px 0px 0px " + style + ", -1px 0px 0px 0px " + style,
                );
            $messages
                .children(".date_row")
                .css(
                    "box-shadow",
                    "inset 2px 0px 0px 0px " + style + ", -1px 0px 0px 0px " + style,
                );
            $label.removeClass("dark_background");
            $label.addClass(color_class.get_css_class(color));
            $label.css({background: recipient_bar_color, "border-left-color": recipient_bar_color});
        }
    }
}

function update_stream_privacy_color(id, color) {
    color = get_stream_privacy_icon_color(color);
    $(`.stream-privacy-${CSS.escape(id)}`).css("color", color);
}

function update_historical_message_color(stream_name, color) {
    update_table_stream_color($(".focused_table"), stream_name, color);
    if ($(".focused_table").attr("id") !== "#zhome") {
        update_table_stream_color($("#zhome"), stream_name, color);
    }
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

export function update_stream_color(sub, color, {update_historical = false} = {}) {
    sub.color = color;
    const stream_id = sub.stream_id;
    // The swatch in the subscription row header.
    $(`.stream-row[data-stream-id='${CSS.escape(stream_id)}'] .icon`).css(
        "background-color",
        color,
    );
    // The swatch in the color picker.
    set_colorpicker_color(
        $(
            `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
                stream_id,
            )}'] .colorpicker`,
        ),
        color,
    );
    $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
            stream_id,
        )}'] .large-icon`,
    ).css("color", color);

    if (update_historical) {
        update_historical_message_color(sub.name, color);
    }
    update_stream_privacy_color(stream_id, color);
    message_view_header.colorize_message_view_header();
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
