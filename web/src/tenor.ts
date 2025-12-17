import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_gif_picker_ui from "../templates/gif_picker_ui.hbs";

import * as gif_picker_ui from "./gif_picker_ui.ts";
import * as popover_menus from "./popover_menus.ts";
import * as rows from "./rows.ts";
import * as scroll_util from "./scroll_util.ts";
import * as ui_util from "./ui_util.ts";

export type TenorPickerState = {
    // Only used if popover called from edit message, otherwise it is `undefined`.
    edit_message_id: number | undefined;
    next_pos_identifier: string | number | undefined;
    is_loading_more: boolean;
    popover_instance: tippy.Instance | undefined;
    current_search_term: undefined | string;
    // Stores the index of the last GIF that is part of the grid.
    last_gif_index: number;
};

const picker_state: TenorPickerState = {
    // Only used if popover called from edit message, otherwise it is `undefined`.
    edit_message_id: undefined,
    next_pos_identifier: undefined,
    is_loading_more: false,
    popover_instance: undefined,
    current_search_term: undefined,
    // Stores the index of the last GIF that is part of the grid.
    last_gif_index: -1,
};

export type TenorPayload = {
    key: string;
    client_key: string;
    limit: string;
    media_filter: string;
    locale: string;
    contentfilter: string;
    pos?: string | number | undefined;
    q?: string;
};

export function get_tenor_picker_state(): TenorPickerState {
    return picker_state;
}

export function is_popped_from_edit_message(): boolean {
    return (
        picker_state.popover_instance !== undefined && picker_state.edit_message_id !== undefined
    );
}

export function focus_current_edit_message(): void {
    assert(picker_state.edit_message_id !== undefined);
    $(`#edit_form_${CSS.escape(`${picker_state.edit_message_id}`)} .message_edit_content`).trigger(
        "focus",
    );
}

function toggle_tenor_popover(target: HTMLElement): void {
    popover_menus.toggle_popover_menu(
        target,
        {
            theme: "popover-menu",
            placement: "top",
            onCreate(instance) {
                instance.setContent(ui_util.parse_html(render_gif_picker_ui({is_giphy: false})));
                $(instance.popper).addClass("tenor-popover");
            },
            onShow(instance) {
                picker_state.popover_instance = instance;
                const $popper = $(instance.popper).trigger("focus");
                const debounced_search = _.debounce((search_term: string) => {
                    gif_picker_ui.update_grid_with_search_term(picker_state, search_term);
                }, 300);
                const $click_target = $(instance.reference);
                if ($click_target.parents(".message_edit_form").length === 1) {
                    // Store message id in global variable edit_message_id so that
                    // its value can be further used to correctly find the message textarea element.
                    picker_state.edit_message_id = rows.id($click_target.parents(".message_row"));
                } else {
                    picker_state.edit_message_id = undefined;
                }

                $(document).one("compose_canceled.zulip compose_finished.zulip", () => {
                    gif_picker_ui.hide_gif_picker_popover(picker_state);
                });

                $popper.on("keyup", "#gif-search-query", (e) => {
                    assert(e.target instanceof HTMLInputElement);
                    if (e.key === "ArrowDown") {
                        // Trigger arrow key based navigation on the grid by focusing
                        // the first grid element.
                        gif_picker_ui.focus_gif_at_index(0, picker_state);
                        return;
                    }
                    debounced_search(e.target.value);
                });
                $popper.on("click", ".tenor-gif", (e) => {
                    assert(e.currentTarget instanceof HTMLElement);
                    gif_picker_ui.handle_gif_click(e.currentTarget, picker_state);
                });
                $popper.on("click", "#gif-search-clear", (e) => {
                    e.stopPropagation();
                    $("#gif-search-query").val("");
                    gif_picker_ui.update_grid_with_search_term(picker_state, "");
                });
                $popper.on("keydown", ".tenor-gif", (e) => {
                    gif_picker_ui.handle_keyboard_navigation_on_gif(e, picker_state);
                });
            },
            onMount(instance) {
                gif_picker_ui.render_default_gifs(false, picker_state);
                const $popper = $(instance.popper);
                $popper.find("#gif-search-query").trigger("focus");

                const scroll_element = scroll_util.get_scroll_element(
                    $(".gif-scrolling-container"),
                )[0];
                assert(scroll_element instanceof HTMLElement);

                scroll_element.addEventListener("scroll", () => {
                    if (
                        scroll_element.scrollTop + scroll_element.clientHeight >
                        scroll_element.scrollHeight - scroll_element.clientHeight
                    ) {
                        if (picker_state.is_loading_more) {
                            return;
                        }
                        if (picker_state.current_search_term === undefined) {
                            gif_picker_ui.render_default_gifs(true, picker_state);
                            return;
                        }
                        gif_picker_ui.update_grid_with_search_term(
                            picker_state,
                            picker_state.current_search_term,
                            true,
                        );
                    }
                });
            },
            onHidden() {
                gif_picker_ui.hide_gif_picker_popover(picker_state);
            },
        },
        {
            show_as_overlay_on_mobile: true,
            show_as_overlay_always: false,
        },
    );
}

function register_click_handlers(): void {
    $("body").on(
        "click",
        ".compose_control_button.compose-gif-icon-tenor",
        function (this: HTMLElement) {
            toggle_tenor_popover(this);
        },
    );
}

export function initialize(): void {
    register_click_handlers();
}
