import $ from "jquery";
import assert from "minimalistic-assert";

import render_color_picker_popover from "../templates/popovers/color_picker_popover.hbs";

import * as blueslip from "./blueslip";
import * as popover_menus from "./popover_menus";
import * as stream_settings_api from "./stream_settings_api";
import * as ui_util from "./ui_util";

const stream_color_palette = [
    "a47462",
    "c2726a",
    "e4523d",
    "e7664d",
    "ee7e4a",
    "f4ae55",
    "76ce90",
    "53a063",
    "94c849",
    "bfd56f",
    "fae589",
    "f5ce6e",
    "a6dcbf",
    "addfe5",
    "a6c7e5",
    "4f8de4",
    "95a5fd",
    "b0a5fd",
    "c2c2c2",
    "c8bebf",
    "c6a8ad",
    "e79ab5",
    "bd86e5",
    "9987e1",
];

export function initialize(): void {
    popover_menus.register_popover_menu(".choose_stream_color", {
        theme: "popover-menu",
        placement: "right",
        onShow(instance) {
            popover_menus.popover_instances.color_picker_popover = instance;
            popover_menus.on_show_prep(instance);

            instance.setContent(
                ui_util.parse_html(
                    render_color_picker_popover({
                        stream_color_palette,
                    }),
                ),
            );
        },
        onMount(instance) {
            const $reference = $(instance.reference);
            const $popper = $(instance.popper);

            const $color_picker = $popper.find(".color-picker");
            const $colorpicker_preview = $popper.find(".color-picker-preview");
            const $color_swatch_options = $popper.find(".color-swatch-option");

            const stream_id = Number.parseInt($reference.attr("data-stream-id")!, 10);
            const color = $reference.attr("data-stream-color")!;

            $color_picker.val(color);
            $colorpicker_preview.css("background-color", color);

            $color_swatch_options.each((_index, color_swatch_option) => {
                const $color_swatch_option = $(color_swatch_option);
                const swatch_color = $color_swatch_option.attr("data-color")!;
                $color_swatch_option.css("background-color", swatch_color);
                if (swatch_color === color) {
                    $color_swatch_option.addClass("current-color-swatch-option");
                }
            });

            $popper.on("click focus", ".color-swatch-option", (e) => {
                const color = $(e.currentTarget).attr("data-color")!;
                $color_picker.val(color);
                $colorpicker_preview.css("background-color", color);
                $popper
                    .find(".current-color-swatch-option")
                    .removeClass("current-color-swatch-option");
                $(e.currentTarget).addClass("current-color-swatch-option");
            });

            $popper.on("input", ".color-picker", (e) => {
                assert(e.target instanceof HTMLInputElement);
                const new_color = $(e.target).val();
                if (!new_color) {
                    blueslip.error("Invalid color picker value");
                    return;
                }
                $colorpicker_preview.css("background-color", new_color);
            });

            $popper.on("click", ".apply-stream-color", () => {
                const new_color = $color_picker.val()?.toString();
                if (!new_color) {
                    blueslip.error("Invalid color picker value");
                    return;
                }
                if (new_color === color) {
                    return;
                }
                stream_settings_api.set_color(stream_id, new_color);
                $reference.attr("data-stream-color", new_color);
            });
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.color_picker_popover = null;
        },
    });
}
