import $ from "jquery";

import * as color_class from "./color_class";
import * as message_view_header from "./message_view_header";
import * as subs from "./subs";

function update_table_stream_color(table, stream_name, color) {
    // This is ugly, but temporary, as the new design will make it
    // so that we only have color in the headers.
    const style = color;

    const stream_labels = $("#floating_recipient_bar").add(table).find(".stream_label");

    for (const label of stream_labels) {
        const $label = $(label);
        if ($label.text().trim() === stream_name) {
            const messages = $label.closest(".recipient_row").children(".message_row");
            messages
                .children(".messagebox")
                .css(
                    "box-shadow",
                    "inset 2px 0px 0px 0px " + style + ", -1px 0px 0px 0px " + style,
                );
            messages
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

function hex(x) {
    return isNaN(x) ? "00" : Number(x).toString(16).padStart(2, "0");
}

function rgb2hex(rgb) {
    rgb = rgb.match(/^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/);
    return "#" + hex(rgb[1]) + hex(rgb[2]) + hex(rgb[3]);
}

export function update_stream_color(sub, color, {update_historical = false} = {}) {
    sub.color = color;
    const stream_id = sub.stream_id;

    $(".stream-row[data-stream-id='" + stream_id + "'] .icon").css('background-color', color);
    $("#subscription_overlay .subscription_settings[data-stream-id='" + stream_id + "'] .large-icon").css("color", color);

    if (update_historical) {
        update_historical_message_color(sub.name, color);
    }
    update_stream_sidebar_swatch_color(stream_id, color);
    message_view_header.colorize_message_view_header();
}

$("body").on("change", "#stream_color_picker", (e) => {
    const color = e.target.value;
    const stream_id = Number.parseInt(e.target.getAttribute("stream_id"), 10);
    subs.set_color(stream_id, color);
});

$("body").on("click", (e) => {
    if (e.target.matches("#custom_color")) {
        const color_picker = $("body").find("#stream_color_picker");
        $(color_picker).click();
    }

    if (
        e.target.matches("#color_picker") ||
        e.target.matches("#color_swatch") ||
        e.target.matches("#color_dropdown")
    ) {
        $("body").find(".color_picker_body").toggleClass("visible");
    } else if (
        !(
            e.target.class === "color_picker_body" ||
            $(e.target).parents(".color_picker_body").length
        ) &&
        $("body").find(".color_picker_body").hasClass("visible")
    ) {
        $("body").find(".color_picker_body").removeClass("visible");
    }

    if (e.target.matches(".presets")) {
        const color = $(e.target).css("background-color");
        const stream_id = Number.parseInt($(e.target).parent().attr("stream_id"), 10);
        subs.set_color(stream_id, rgb2hex(color));
    }
});
