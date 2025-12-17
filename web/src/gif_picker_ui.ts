import type { TenorPickerState } from "./tenor";

export function hide_gif_picker_popover(picker_state:TenorPickerState): boolean {
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