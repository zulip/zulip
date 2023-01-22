import $ from "jquery";

import * as color_class from "./color_class";
import {$t} from "./i18n";
import * as message_view_header from "./message_view_header";
import * as stream_settings_ui from "./stream_settings_ui";

function update_table_stream_color(table, stream_name, color) {
    // This is ugly, but temporary, as the new design will make it
    // so that we only have color in the headers.
    const style = color;

    const $stream_labels = $("#floating_recipient_bar").add(table).find(".stream_label");

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
            $label.css({background: style, "border-left-color": style});
            $label.removeClass("dark_background");
            $label.addClass(color_class.get_css_class(color));
        }
    }
}

function update_stream_sidebar_swatch_color(id, color) {
    $(`#stream_sidebar_swatch_${CSS.escape(id)}`).css("background-color", color);
    $(`#stream_sidebar_privacy_swatch_${CSS.escape(id)}`).css("color", color);
}

function update_historical_message_color(stream_name, color) {
    update_table_stream_color($(".focused_table"), stream_name, color);
    if ($(".focused_table").attr("id") !== "#zhome") {
        update_table_stream_color($("#zhome"), stream_name, color);
    }
}

const STREAM_HUE_LIST = [5, 45, 95, 160, 205, 280, 325];

const stream_color_palette = [];

for (let index = 0; index < 5; index += 1) {
    const lightness = 80 - 10 * index;
    const saturation = 75 - 13 * index;
    for (const hue of STREAM_HUE_LIST) {
        const hsl = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
        stream_color_palette.push(hsl);
    }
    const hsl_bw = `hsl(0, 0%, ${lightness}%)`;
    stream_color_palette.push(hsl_bw);
}

const subscriptions_table_colorpicker_options = {
    clickoutFiresChange: true,
    showPalette: true,
    showInput: true,
    palette: stream_color_palette,
    showPaletteOnly: true,
    togglePaletteOnly: true,
    preferredFormat: "hex",
    togglePaletteMoreText: "Custom color",
    togglePaletteLessText: "Close picker",
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
    showPaletteOnly: true,
    togglePaletteOnly: true,
    preferredFormat: "hex",
    togglePaletteMoreText: "Custom color",
    togglePaletteLessText: "Close picker",
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
