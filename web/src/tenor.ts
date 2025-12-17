import $ from "jquery";
import assert from "minimalistic-assert";

import * as gif_picker_ui from "./gif_picker_ui.ts";

const picker_state: gif_picker_ui.GifPickerState = {
    // Only used if popover called from edit message, otherwise it is `undefined`.
    edit_message_id: undefined,
    next_pos_identifier: undefined,
    is_loading_more: false,
    popover_instance: undefined,
    current_search_term: undefined,
    // Stores the index of the last GIF that is part of the grid.
    last_gif_index: -1,
    gif_provider: "tenor",
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

export function get_tenor_picker_state(): gif_picker_ui.GifPickerState {
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

function register_click_handlers(): void {
    $("body").on(
        "click",
        ".compose_control_button.compose-gif-icon-tenor",
        function (this: HTMLElement) {
            gif_picker_ui.toggle_gif_popover(this, picker_state);
        },
    );
}

export function initialize(): void {
    register_click_handlers();
}
