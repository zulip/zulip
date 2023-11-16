// Tracks whether the next scroll that will complete is initiated by
// code, not the user, and thus should avoid moving the selected
// message.
export let update_selection_on_next_scroll = true;

export function set_update_selection_on_next_scroll(value: boolean): void {
    update_selection_on_next_scroll = value;
}

// Whether a keyboard shortcut is triggering a message feed scroll event.
export let keyboard_triggered_current_scroll = false;

export function set_keyboard_triggered_current_scroll(value: boolean): void {
    keyboard_triggered_current_scroll = value;
}

// Whether a scroll is currently occurring.
export let actively_scrolling = false;

export function set_actively_scrolling(value: boolean): void {
    actively_scrolling = value;
}
