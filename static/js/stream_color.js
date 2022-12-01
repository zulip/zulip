import $ from "jquery";

import {$t} from "./i18n";
import * as message_view_header from "./message_view_header";
import * as stream_settings_ui from "./stream_settings_ui";

function update_stream_sidebar_swatch_color(id, color) {
    $(`#stream_sidebar_swatch_${CSS.escape(id)}`).css("background-color", color);
    $(`#stream_sidebar_privacy_swatch_${CSS.escape(id)}`).css("color", color);
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

export function update_stream_color(sub, color) {
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

    update_stream_sidebar_swatch_color(stream_id, color);
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
