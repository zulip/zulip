import $ from "jquery";
import _ from "lodash";
import type * as tippy from "tippy.js";

import render_group_color_picker_popover from "../templates/popovers/group_color_picker_popover.hbs";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as popover_menus from "./popover_menus.ts";
import * as stream_color from "./stream_color.ts";
import * as ui_util from "./ui_util.ts";
import * as user_group_edit from "./user_group_edit.ts";
import * as user_groups from "./user_groups.ts";

const update_group_color_preview = (color: string, $popper: JQuery): void => {
    const preview_color = user_groups.get_user_name_color(color);
    $popper.find(".group-color-preview-name").css("color", preview_color);
};

const update_group_color_debounced = _.debounce(
    (new_color: string, group_id: number, $popper: JQuery) => {
        update_group_color_preview(new_color, $popper);
        channel.patch({
            url: "/json/user_groups/" + group_id,
            data: {color: new_color},
        });
    },
    200,
    {leading: false},
);

export function toggle_color_picker_popover(
    target: tippy.ReferenceElement,
    group_id: number,
): void {
    const group = user_groups.get_user_group_from_id(group_id);

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
            popover_menus.popover_instances.color_picker_popover = instance;
            popover_menus.on_show_prep(instance);

            const group_name = user_groups.get_display_group_name(group.name);
            const group_color = group.color;
            const preview_color = user_groups.get_user_name_color(group_color);
            const stream_color_palette = stream_color.stream_color_palette;

            instance.setContent(
                ui_util.parse_html(
                    render_group_color_picker_popover({
                        group_id,
                        group_name,
                        group_color,
                        group_color_for_input: group_color || "#000000",
                        preview_color,
                        stream_color_palette,
                        has_color: group_color !== "",
                    }),
                ),
            );
        },
        onMount(instance) {
            const $popper = $(instance.popper);

            const $color_picker_input = $popper.find(".color-picker-input");
            if (group.color) {
                $color_picker_input.val(group.color);
            }

            $popper.on(
                "change",
                "input[name='color-picker-select']",
                function (this: HTMLInputElement, _e: JQuery.Event) {
                    const new_color = $(this).attr("data-swatch-color")!;
                    if (group.color === new_color) {
                        return;
                    }
                    $color_picker_input.val(new_color);
                    update_group_color_debounced(new_color, group_id, $popper);
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
                    update_group_color_debounced(new_color, group_id, $popper);
                },
            );

            $popper.on("click", ".remove-group-color", () => {
                channel.patch({
                    url: "/json/user_groups/" + group_id,
                    data: {color: ""},
                });
                popover_menus.hide_current_popover_if_visible(instance);
            });

            $popper.on("click", ".color_picker_confirm_button", () => {
                popover_menus.hide_current_popover_if_visible(instance);
            });
        },
        onHidden(instance) {
            instance.destroy();
            popover_menus.popover_instances.color_picker_popover = null;
            user_group_edit.update_group_color_ui(group_id);
        },
    });
}

export function initialize(): void {
    $("body").on(
        "click",
        ".choose_group_color",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.stopPropagation();
            e.preventDefault();

            const group_id = Number.parseInt($(this).attr("data-group-id")!, 10);
            toggle_color_picker_popover(this, group_id);
        },
    );
    $("body").on(
        "click",
        ".group-color-label",
        function (this: HTMLElement, e: JQuery.ClickEvent) {
            e.stopPropagation();
            e.preventDefault();
            // The button is inside a sibling div.group-color-controls,
            // not a direct sibling of the label, so we traverse up.
            const $button = $(this).closest(".input-group").find(".choose_group_color");
            $button.trigger("click");
        },
    );
}
