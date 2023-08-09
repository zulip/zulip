import {colord, extend} from "colord";
import lchPlugin from "colord/plugins/lch";
import mixPlugin from "colord/plugins/mix";
import $ from "jquery";

import {$t} from "./i18n";
import * as inbox_util from "./inbox_util";
import * as message_lists from "./message_lists";
import * as message_view_header from "./message_view_header";
import * as overlays from "./overlays";
import * as row from "./rows";
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

function update_table_message_recipient_stream_color(table, stream_name, recipient_bar_color) {
    const $stream_labels = table.find(".stream_label");
    for (const label of $stream_labels) {
        const $label = $(label);
        if ($label.text().trim() === stream_name) {
            $label
                .closest(".message_header_stream .message-header-contents")
                .css({background: recipient_bar_color});
        }
    }
}

function update_stream_privacy_color(id, color) {
    $(`.stream-privacy-original-color-${CSS.escape(id)}`).css("color", color);
    color = get_stream_privacy_icon_color(color);
    // `modified-color` is only used in recipient bars.
    $(`.stream-privacy-modified-color-${CSS.escape(id)}`).css("color", color);
}

function update_message_recipient_color(stream_name, color) {
    const recipient_color = get_recipient_bar_color(color);
    for (const msg_list of message_lists.all_rendered_message_lists()) {
        const $table = row.get_table(msg_list.table_name);
        update_table_message_recipient_stream_color($table, stream_name, recipient_color);
    }

    // Update color for drafts if open.
    if (overlays.drafts_open()) {
        update_table_message_recipient_stream_color(
            $(".drafts-container"),
            stream_name,
            recipient_color,
        );
    }

    if (inbox_util.is_visible()) {
        const stream_id = stream_data.get_stream_id(stream_name);
        $(`#inbox-stream-header-${stream_id}`).css("background", recipient_color);
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

    update_message_recipient_color(sub.name, color);
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
