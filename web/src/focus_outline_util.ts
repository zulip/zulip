const NAVIGATION_KEYS = new Set([
    "tab",
    "shift_tab",
    "up_arrow",
    "down_arrow",
    "left_arrow",
    "right_arrow",
    "vim_up",
    "vim_down",
    "vim_left",
    "vim_right",
    "page_up",
    "page_down",
]);

/**
 * Remove the `no-visible-focus-outlines` CSS class from the given
 * container when the user presses a navigation key, so that
 * subsequent `:focus` outlines become visible.
 *
 * Returns `true` when the class was present and has just been
 * removed (i.e. this is the first navigation keypress), so callers
 * can decide whether to skip the normal navigation action.
 */
export function maybe_show_focus_outlines($container: JQuery, input_key: string): boolean {
    if ($container.hasClass("no-visible-focus-outlines") && NAVIGATION_KEYS.has(input_key)) {
        $container.removeClass("no-visible-focus-outlines");
        return true;
    }
    return false;
}
