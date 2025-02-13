import $ from "jquery";
import _ from "lodash";
import type * as tippy from "tippy.js";

import render_color_picker_popover from "../templates/popovers/color_picker_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as popover_menus from "./popover_menus.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as ui_util from "./ui_util.ts";

const update_color_picker_preview = (color: string, $popper: JQuery): void => {
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

export function handle_keyboard(key: string): void {
    const instance = popover_menus.get_color_picker_popover();
    if (!instance) {
        return;
    }
    const $items = popover_menus.get_popover_items_for_instance(instance);
    if (!$items) {
        return;
    }

    const $element = $items.filter(":focus");

    if ($element.hasClass("color-swatch-label")) {
        const color_hex_code = $element.attr("data-swatch-color");
        if (!color_hex_code) {
            return;
        }
        const color_palette_matrix = stream_color.stream_color_palette;
        if (!color_palette_matrix) {
            return;
        }
        const max_row = color_palette_matrix.length - 1;
        const max_column = color_palette_matrix[0]!.length - 1;
        const row = Number.parseInt($element.attr("data-row")!, 10);
        const column = Number.parseInt($element.attr("data-column")!, 10);

        const $swatch_color_list = $(instance.popper).find(".color-swatch-list");

        if (key === "down_arrow" || key === "vim_down") {
            if (row < max_row) {
                $swatch_color_list
                    .find(`[data-row="${row + 1}"][data-column="${column}"]`)
                    .trigger("focus");
            } else if (row === max_row) {
                $swatch_color_list
                    .parent()
                    .nextAll(".link-item")
                    .find("[tabindex='0']")
                    .trigger("focus");
            }
            return;
        }

        if (key === "up_arrow" || key === "vim_up") {
            if (row > 0) {
                $swatch_color_list
                    .find(`[data-row="${row - 1}"][data-column="${column}"]`)
                    .trigger("focus");
            } else {
                $(instance.popper).find(".color_picker_confirm_button").trigger("focus");
            }
            return;
        }

        if (key === "left_arrow" || key === "vim_left") {
            if (column > 0) {
                $swatch_color_list
                    .find(`[data-row="${row}"][data-column="${column - 1}"]`)
                    .trigger("focus");
            } else {
                $swatch_color_list
                    .find(`[data-row="${row - 1}"][data-column="${max_column}"]`)
                    .trigger("focus");
            }
            return;
        }

        if (key === "right_arrow" || key === "vim_right") {
            if (column < max_column) {
                $swatch_color_list
                    .find(`[data-row="${row}"][data-column="${column + 1}"]`)
                    .trigger("focus");
            } else {
                $swatch_color_list
                    .find(`[data-row="${row + 1}"][data-column="0"]`)
                    .trigger("focus");
            }
            return;
        }
    }

    popover_menus.popover_items_handle_keyboard(key, $items);
}

export function toggle_color_picker_popover(
    target: tippy.ReferenceElement,
    stream_id: number,
): void {
    popover_menus.toggle_popover_menu(target, {
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
            ui_util.show_left_sidebar_menu_icon(target);
            popover_menus.popover_instances.color_picker_popover = instance;
            popover_menus.on_show_prep(instance);

            const stream_name = stream_data.get_stream_name_from_id(stream_id);
            const color = stream_data.get_color(stream_id);
            const recipient_bar_color = stream_color.get_recipient_bar_color(color);
            const stream_privacy_icon_color = stream_color.get_stream_privacy_icon_color(color);
            const invite_only = stream_data.is_invite_only_by_stream_id(stream_id);
            const is_web_public = stream_data.is_web_public(stream_id);
            const stream_color_palette = stream_color.stream_color_palette;

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
            const $popper = $(instance.popper);

            const $color_picker_input = $popper.find(".color-picker-input");
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

            $popper.on("click", ".color_picker_confirm_button", () => {
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            instance.destroy();
            ui_util.hide_left_sidebar_menu_icon();
            popover_menus.popover_instances.color_picker_popover = null;
        },
    });
}

export function initialize(): void {
    $("body").on(
        "click",
        ".choose_stream_color",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.stopPropagation();
            e.preventDefault();

            const stream_id = Number.parseInt($(this).attr("data-stream-id")!, 10);

            let target: tippy.ReferenceElement | undefined;
            if (popover_menus.is_stream_actions_popover_displayed()) {
                // If the stream actions popover is open, we want to open the color picker popover
                // from the same reference element as that of the stream actions popover so that
                // the color picker popover replaces the stream actions popover in-place.
                // This avoids the cluttering of the UI with multiple popovers, given that we can
                // also open the browser native color picker from the color picker popover.
                target = popover_menus.popover_instances.stream_actions_popover?.reference;
                popover_menus.hide_current_popover_if_visible(
                    popover_menus.popover_instances.stream_actions_popover,
                );
            }

            // If the stream actions popover is not open, we want to open the color picker popover
            // from the target of the click event.
            toggle_color_picker_popover(target ?? this, stream_id);
        },
    );
    $("body").on(
        "click",
        ".channel-color-label",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.stopPropagation();
            e.preventDefault();
            const $button = $(this).siblings(".choose_stream_color");
            $button.trigger("click");
        },
    );
}
