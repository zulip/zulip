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

export function focus_gif_at_index(index: number, picker_state: TenorPickerState): void {
    if (index < 0 || index > picker_state.last_gif_index) {
        assert(picker_state.popover_instance !== undefined);
        const $popper = $(picker_state.popover_instance.popper);
        // Just trigger focus on the search input because there are no GIFs
        // above or below.
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }

    const $target_gif = $(`img.tenor-gif[data-gif-index='${index}']`);
    $target_gif.trigger("focus");
}

export function handle_keyboard_navigation_on_gif(
    e: JQuery.KeyDownEvent,
    picker_state: TenorPickerState,
): void {
    e.stopPropagation();
    assert(e.currentTarget instanceof HTMLElement);
    const key = e.key;
    const is_alpha_numeric = /^[a-zA-Z0-9]$/i.test(key);
    if (is_alpha_numeric) {
        // This implies that the user is focused on some GIF
        // but wants to continue searching.
        assert(picker_state.popover_instance !== undefined);
        const $popper = $(picker_state.popover_instance.popper);
        $popper.find("#gif-search-query").trigger("focus");
        return;
    }
    if (key === "Enter" || key === " " || key === "Spacebar") {
        // Meant to avoid page scroll on pressing space.
        e.preventDefault();
        handle_gif_click(e.currentTarget, picker_state);
        return;
    }

    const curr_gif_index = Number.parseInt(e.currentTarget.dataset["gifIndex"]!, 10);
    switch (key) {
        case "ArrowRight": {
            focus_gif_at_index(curr_gif_index + 1, picker_state);
            break;
        }
        case "ArrowLeft": {
            focus_gif_at_index(curr_gif_index - 1, picker_state);
            break;
        }
        case "ArrowUp": {
            focus_gif_at_index(curr_gif_index - 3, picker_state);
            break;
        }
        case "ArrowDown": {
            focus_gif_at_index(curr_gif_index + 3, picker_state);
            break;
        }
    }
}
