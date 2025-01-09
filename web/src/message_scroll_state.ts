export let update_selection_on_next_scroll = true;

export function set_update_selection_on_next_scroll(value: boolean): void {
    update_selection_on_next_scroll = value;
}

export let keyboard_triggered_current_scroll = false;

export function set_keyboard_triggered_current_scroll(value: boolean): void {
    keyboard_triggered_current_scroll = value;
}

export let actively_scrolling = false;

export function set_actively_scrolling(value: boolean): void {
    actively_scrolling = value;
}

export function is_message_partially_visible($message_row: JQuery): boolean {
    const viewport_info = message_viewport.message_viewport_info();
    const message_top = $message_row.get_offset_to_window().top;
    const message_bottom = message_top + ($message_row.outerHeight(true) ?? 0);

    return (
        (message_top >= viewport_info.visible_top && message_top < viewport_info.visible_bottom) ||
        (message_bottom > viewport_info.visible_top && message_bottom <= viewport_info.visible_bottom)
    );
}
