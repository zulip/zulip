import $ from "jquery";

import render_color_picker_popover from "../templates/popovers/color_picker_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as popover_menus from "./popover_menus.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as ui_util from "./ui_util.ts";

function update_color_picker_preview(color: string, $popper: JQuery): void {
    const $custom_color_option_icon = $popper.find(".custom-color-option-icon");
    $custom_color_option_icon.css("background-color", color);
    const $stream_header = $popper.find(".message_header_stream");
    stream_color.update_stream_recipient_color($stream_header, color);
}

export function initialize(): void {
    popover_menus.register_popover_menu(".choose_stream_color", {
        theme: "popover-menu",
        placement: "right",
        popperOptions: {
            modifiers: [
                {
                    name: "flip",
                    options: {
                        fallbackPlacements: ["bottom", "left"],
                    },
                },
            ],
        },
        onShow(instance) {
            popover_menus.popover_instances.color_picker_popover = instance;
            popover_menus.on_show_prep(instance);

            const $reference = $(instance.reference);
            const stream_id = Number.parseInt($reference.attr("data-stream-id")!, 10);
            const stream_name = stream_data.get_stream_name_from_id(stream_id);
            const color = stream_data.get_color(stream_id);
            const recipient_bar_color = stream_color.get_recipient_bar_color(color);
            const stream_privacy_icon_color = stream_color.get_stream_privacy_icon_color(color);
            const invite_only = stream_data.is_invite_only_by_stream_id(stream_id);
            const is_web_public = stream_data.is_web_public(stream_id);
            const stream_color_palette = stream_color.stream_color_palette.flat();

            instance.setContent(
                ui_util.parse_html(
                    render_color_picker_popover({
                        stream_id,
                        stream_name,
                        recipient_bar_color,
                        stream_privacy_icon_color,
                        invite_only,
                        is_web_public,
                        stream_color_palette,
                    }),
                ),
            );
        },
        onMount(instance) {
            const $reference = $(instance.reference);
            const $popper = $(instance.popper);

            const $color_picker = $popper.find(".color-picker");
            const $custom_color_option_icon = $popper.find(".custom-color-option-icon");
            const $color_swatch_options = $popper.find(".color-swatch-option");

            const stream_id = Number.parseInt($reference.attr("data-stream-id")!, 10);
            const color = stream_data.get_color(stream_id);

            $color_picker.val(color);
            $custom_color_option_icon.css("background-color", color);

            $color_swatch_options.each((_index, color_swatch_option) => {
                const $color_swatch_option = $(color_swatch_option);
                const swatch_color = $color_swatch_option.attr("data-color")!;
                $color_swatch_option.css("background-color", swatch_color);
                if (swatch_color === color) {
                    $color_swatch_option.addClass("current-color-swatch-option");
                }
            });

            $popper.on("click focus", ".color-swatch-option", function (this: HTMLElement) {
                const color = $(this).attr("data-color")!;
                $color_picker.val(color);
                update_color_picker_preview(color, $popper);
                $popper
                    .find(".current-color-swatch-option")
                    .removeClass("current-color-swatch-option");
                $(this).addClass("current-color-swatch-option");
            });

            $popper.on(
                "input",
                ".color-picker",
                function (this: HTMLInputElement, _e: JQuery.Event) {
                    const new_color = $(this).val();
                    if (!new_color) {
                        blueslip.error("Invalid color picker value");
                        return;
                    }
                    update_color_picker_preview(new_color, $popper);
                },
            );

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
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.color_picker_popover = null;
        },
    });
}
