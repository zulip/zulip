import $ from "jquery";
import _ from "lodash";

import render_color_picker_popover from "../templates/popovers/color_picker_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as popover_menus from "./popover_menus.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as ui_util from "./ui_util.ts";

const update_color_picker_preview = (color: string, $popper: JQuery): void => {
    const $custom_color_option_icon = $popper.find(".custom-color-option-icon");
    $custom_color_option_icon.css("background-color", color);
    const $stream_header = $popper.find(".message_header_stream");
    stream_color.update_stream_recipient_color($stream_header, color);
};

const update_stream_color_debounced = _.debounce(
    (new_color: string, stream_id: number, $popper: JQuery) => {
        update_color_picker_preview(new_color, $popper);
        stream_settings_api.set_color(stream_id, new_color);
    },
    // Wait for 200ms of inactivity
    200,
    // Don't execute immediately on the first color change
    {leading: false},
);

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
                        stream_color: color,
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

            const $color_picker_input = $popper.find(".color-picker-input");
            const stream_id = Number.parseInt($reference.attr("data-stream-id")!, 10);
            const color = stream_data.get_color(stream_id);

            $color_picker_input.val(color);

            $popper.on(
                "change",
                "input[name='color-picker-select']",
                function (this: HTMLInputElement, _e: JQuery.Event) {
                    const prev_color = stream_data.get_color(stream_id);
                    const new_color = $(this).attr("data-swatch-color")!;
                    if (prev_color === new_color) {
                        return;
                    }
                    $color_picker_input.val(new_color);
                    update_stream_color_debounced(new_color, stream_id, $popper);
                },
            );

            $popper.on(
                "input",
                ".color-picker-input",
                function (this: HTMLInputElement, _e: JQuery.Event) {
                    const new_color = $(this).val();
                    if (!new_color) {
                        blueslip.error("Invalid color picker value");
                        return;
                    }
                    const $swatch_color_checked = $popper.find(
                        "input[name='color-picker-select']:checked",
                    );
                    $swatch_color_checked.prop("checked", false);
                    update_stream_color_debounced(new_color, stream_id, $popper);
                },
            );
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.color_picker_popover = null;
        },
    });
}
