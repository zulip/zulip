import $ from "jquery";
import assert from "minimalistic-assert";

import * as compose_ui from "./compose_ui.ts";
import type {TenorPickerState} from "./tenor";

export function hide_gif_picker_popover(picker_state: TenorPickerState): boolean {
    // Returns `true` if the popover was open.
    if (picker_state.popover_instance) {
        picker_state.popover_instance.destroy();
        picker_state.popover_instance = undefined;
        picker_state.edit_message_id = undefined;
        picker_state.next_pos_identifier = undefined;
        picker_state.current_search_term = undefined;
        picker_state.is_loading_more = false;
        return true;
    }
    return false;
}

export function handle_gif_click(img_element: HTMLElement, picker_state: TenorPickerState): void {
    const insert_url = img_element.dataset["insertUrl"];
    assert(insert_url !== undefined);

    let $textarea = $<HTMLTextAreaElement>("textarea#compose-textarea");
    if (picker_state.edit_message_id !== undefined) {
        $textarea = $(
            `#edit_form_${CSS.escape(`${picker_state.edit_message_id}`)} .message_edit_content`,
        );
    }

    compose_ui.insert_syntax_and_focus(`[](${insert_url})`, $textarea, "block", 1);
    hide_gif_picker_popover(picker_state);
}
